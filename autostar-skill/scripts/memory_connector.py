#!/usr/bin/env python3
"""
Minimal remote memory connector surface for Claude.ai-compatible deployments.
"""

from __future__ import annotations

import argparse
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

try:
    from memory_backend import MemoryBackend
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from .memory_backend import MemoryBackend


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "lookup_priors",
            "description": "Retrieve disposition priors for a problem class and anticipated action intents.",
            "inputSchema": {
                "type": "object",
                "required": ["project_id", "problem_class", "problem_description", "anticipated_action_intents"],
                "properties": {
                    "project_id": {"type": "string"},
                    "problem_class": {"type": "string"},
                    "problem_description": {"type": "string"},
                    "anticipated_action_intents": {"type": "array", "items": {"type": "string"}},
                    "goal": {"type": "string"},
                    "artifact_description": {"type": "string"},
                    "context_text": {"type": "string"}
                }
            }
        },
        {
            "name": "fetch_recent_episodes",
            "description": "Fetch recent episodic records for a project, optionally filtered by problem class.",
            "inputSchema": {
                "type": "object",
                "required": ["project_id"],
                "properties": {
                    "project_id": {"type": "string"},
                    "problem_class": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1}
                }
            }
        },
        {
            "name": "append_episode",
            "description": "Append an episode record to the episodic store.",
            "inputSchema": {"type": "object"}
        },
        {
            "name": "write_run_summary",
            "description": "Store a completed-run summary.",
            "inputSchema": {"type": "object"}
        },
        {
            "name": "list_pending_disposition_updates",
            "description": "List pending disposition updates for a project.",
            "inputSchema": {
                "type": "object",
                "properties": {"project_id": {"type": "string"}}
            }
        },
        {
            "name": "apply_approved_updates",
            "description": "Approve and apply pending or explicitly referenced disposition updates.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "update_ids": {"type": "array", "items": {"type": "string"}},
                    "approved_by": {"type": "string"}
                }
            }
        },
        {
            "name": "get_project_state",
            "description": "Fetch compact project-scoped state.",
            "inputSchema": {
                "type": "object",
                "required": ["project_id"],
                "properties": {"project_id": {"type": "string"}}
            }
        },
        {
            "name": "set_project_state",
            "description": "Persist compact project-scoped state.",
            "inputSchema": {"type": "object"}
        }
    ]


class MemoryConnectorHandler(BaseHTTPRequestHandler):
    backend: MemoryBackend
    auth_token: str | None = None

    def _authorized(self) -> bool:
        if not self.auth_token:
            return True
        header = self.headers.get("Authorization", "")
        return header == f"Bearer {self.auth_token}"

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            json_response(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        if not self._authorized():
            json_response(self, HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return
        json_response(
            self,
            HTTPStatus.OK,
            {
                "ok": True,
                "surface": "connector_backed",
                "backend": self.backend.health(),
                "tools": [tool["name"] for tool in tool_definitions()],
            },
        )

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/mcp":
            json_response(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        if not self._authorized():
            json_response(self, HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or "{}")
        response = self._dispatch(payload)
        json_response(self, HTTPStatus.OK, response)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def _dispatch(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params", {})
        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "autostar-memory-connector", "version": "1.0"},
                    "capabilities": {"tools": {}},
                }
            elif method == "ping":
                result = {"ok": True}
            elif method == "tools/list":
                result = {"tools": tool_definitions()}
            elif method == "tools/call":
                result = self._call_tool(params.get("name"), params.get("arguments", {}))
            else:
                raise ValueError(f"unsupported method: {method}")
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": str(exc)},
            }

    def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "lookup_priors":
            result = self.backend.lookup_priors(
                project_id=arguments["project_id"],
                problem_class=arguments["problem_class"],
                anticipated_action_intents=arguments["anticipated_action_intents"],
                problem_description=arguments["problem_description"],
                goal=arguments.get("goal", ""),
                artifact_description=arguments.get("artifact_description", ""),
                context_text=arguments.get("context_text", ""),
                memory_mode="connector_backed",
            )
        elif name == "fetch_recent_episodes":
            result = self.backend.fetch_recent_episodes(
                arguments["project_id"],
                arguments.get("problem_class"),
                arguments.get("limit", 10),
            )
        elif name == "append_episode":
            result = self.backend.append_episode(arguments)
        elif name == "write_run_summary":
            result = self.backend.write_run_summary(arguments)
        elif name == "list_pending_disposition_updates":
            result = self.backend.list_pending_disposition_updates(arguments.get("project_id"))
        elif name == "apply_approved_updates":
            result = self.backend.apply_approved_updates(
                project_id=arguments.get("project_id"),
                update_ids=arguments.get("update_ids"),
                approved_by=arguments.get("approved_by", "connector"),
            )
        elif name == "get_project_state":
            result = self.backend.get_project_state(arguments["project_id"])
        elif name == "set_project_state":
            result = self.backend.set_project_state(arguments)
        else:
            raise ValueError(f"unknown tool: {name}")
        return {"content": [{"type": "json", "json": result}]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve the autostar memory connector")
    parser.add_argument("--db", required=True, help="Path to the SQLite memory backend")
    parser.add_argument("--mirror-dir", help="Mirror export directory")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default=os.environ.get("AUTOSTAR_MEMORY_CONNECTOR_TOKEN"))
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    backend = MemoryBackend(args.db, mirror_dir=args.mirror_dir)
    MemoryConnectorHandler.backend = backend
    MemoryConnectorHandler.auth_token = args.token
    server = ThreadingHTTPServer((args.host, args.port), MemoryConnectorHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - server loop exit
        return 0
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())

