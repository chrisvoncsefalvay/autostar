#!/usr/bin/env python3
"""
Inspect and select a* runtime profiles.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


STRUCTURED_CHOICE_ORDER = {"none": 0, "basic": 1, "full": 2}
FILE_MODE_ORDER = {"none": 0, "limited": 1, "full": 2}
SUPPORT_LEVEL_ORDER = {"unsupported": 0, "reduced": 1, "full": 2}
PROFILE_KEYS = {"runtime", "support_level", "capabilities", "native_mappings", "downgrades"}
RUNTIME_KEYS = {"name", "version"}
CAPABILITY_KEYS = {
    "structured_choice",
    "freeform_input",
    "file_presentation",
    "local_html",
    "subprocess",
    "pause_resume",
    "file_read_write",
    "long_term_memory",
}
MAPPING_KEYS = {
    "choose",
    "ask",
    "present",
    "run",
    "pause",
    "read",
    "write",
    "append",
    "memory_lookup",
    "memory_store",
}


@dataclass
class RuntimeProfile:
    path: Path
    data: dict

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def runtime_name(self) -> str:
        return self.data["runtime"]["name"]

    @property
    def support_level(self) -> str:
        return self.data["support_level"]

    @property
    def capabilities(self) -> dict:
        return self.data["capabilities"]


def default_skill_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def repo_root(skill_dir: Path) -> Path:
    return skill_dir.parent


def schema_path(skill_dir: Path) -> Path:
    return repo_root(skill_dir) / "schemas" / "runtime-profile.schema.json"


def validate_profile_shape(profile: RuntimeProfile) -> list[str]:
    errors: list[str] = []
    data = profile.data

    if set(data.keys()) != PROFILE_KEYS:
        missing = PROFILE_KEYS - set(data.keys())
        extra = set(data.keys()) - PROFILE_KEYS
        if missing:
            errors.append(f"{profile.path.name}: missing top-level keys: {', '.join(sorted(missing))}")
        if extra:
            errors.append(f"{profile.path.name}: unexpected top-level keys: {', '.join(sorted(extra))}")

    runtime = data.get("runtime")
    if not isinstance(runtime, dict):
        errors.append(f"{profile.path.name}: runtime must be an object")
    else:
        missing = RUNTIME_KEYS - set(runtime.keys())
        extra = set(runtime.keys()) - RUNTIME_KEYS
        if missing:
            errors.append(f"{profile.path.name}: runtime missing keys: {', '.join(sorted(missing))}")
        if extra:
            errors.append(f"{profile.path.name}: runtime has unexpected keys: {', '.join(sorted(extra))}")
        if not isinstance(runtime.get("name"), str) or not runtime.get("name", "").strip():
            errors.append(f"{profile.path.name}: runtime.name must be a non-empty string")
        version = runtime.get("version")
        if version is not None and not isinstance(version, str):
            errors.append(f"{profile.path.name}: runtime.version must be a string or null")

    support_level = data.get("support_level")
    if support_level not in SUPPORT_LEVEL_ORDER:
        errors.append(f"{profile.path.name}: invalid support_level '{support_level}'")

    capabilities = data.get("capabilities")
    if not isinstance(capabilities, dict):
        errors.append(f"{profile.path.name}: capabilities must be an object")
    else:
        missing = CAPABILITY_KEYS - set(capabilities.keys())
        extra = set(capabilities.keys()) - CAPABILITY_KEYS
        if missing:
            errors.append(f"{profile.path.name}: capabilities missing keys: {', '.join(sorted(missing))}")
        if extra:
            errors.append(f"{profile.path.name}: capabilities have unexpected keys: {', '.join(sorted(extra))}")

        if capabilities.get("structured_choice") not in STRUCTURED_CHOICE_ORDER:
            errors.append(f"{profile.path.name}: invalid structured_choice")
        if capabilities.get("file_presentation") not in {"inline", "external", "none"}:
            errors.append(f"{profile.path.name}: invalid file_presentation")
        if capabilities.get("local_html") not in {"inline", "external", "none"}:
            errors.append(f"{profile.path.name}: invalid local_html")
        if capabilities.get("file_read_write") not in FILE_MODE_ORDER:
            errors.append(f"{profile.path.name}: invalid file_read_write")
        for key in ("freeform_input", "subprocess", "pause_resume", "long_term_memory"):
            if not isinstance(capabilities.get(key), bool):
                errors.append(f"{profile.path.name}: {key} must be boolean")

    mappings = data.get("native_mappings")
    if not isinstance(mappings, dict):
        errors.append(f"{profile.path.name}: native_mappings must be an object")
    else:
        missing = MAPPING_KEYS - set(mappings.keys())
        extra = set(mappings.keys()) - MAPPING_KEYS
        if missing:
            errors.append(f"{profile.path.name}: native_mappings missing keys: {', '.join(sorted(missing))}")
        if extra:
            errors.append(f"{profile.path.name}: native_mappings have unexpected keys: {', '.join(sorted(extra))}")
        for key, value in mappings.items():
            if value is not None and not isinstance(value, str):
                errors.append(f"{profile.path.name}: native_mappings.{key} must be a string or null")

    downgrades = data.get("downgrades")
    if not isinstance(downgrades, list):
        errors.append(f"{profile.path.name}: downgrades must be an array")
    else:
        for idx, item in enumerate(downgrades):
            if not isinstance(item, dict):
                errors.append(f"{profile.path.name}: downgrade #{idx + 1} must be an object")
                continue
            if set(item.keys()) != {"capability", "effect"}:
                errors.append(f"{profile.path.name}: downgrade #{idx + 1} must contain only capability/effect")
                continue
            for key in ("capability", "effect"):
                if not isinstance(item.get(key), str) or not item[key].strip():
                    errors.append(f"{profile.path.name}: downgrade #{idx + 1} {key} must be a non-empty string")

    return errors


def adapter_path_for(profile: RuntimeProfile, skill_dir: Path) -> Path:
    if profile.stem == "template":
        filename = "adapter-template.md"
    else:
        filename = f"adapter-{profile.stem}.md"
    return skill_dir / "references" / filename


def load_profiles(skill_dir: Path) -> list[RuntimeProfile]:
    profiles_dir = skill_dir / "runtime-profiles"
    profiles: list[RuntimeProfile] = []
    for path in sorted(profiles_dir.glob("*.json")):
        data = json.loads(path.read_text())
        profiles.append(RuntimeProfile(path=path, data=data))
    return profiles


def real_profiles(profiles: list[RuntimeProfile]) -> list[RuntimeProfile]:
    return [profile for profile in profiles if profile.stem != "template"]


def validate_profiles(skill_dir: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    schema = schema_path(skill_dir)
    if not schema.exists():
        errors.append(f"Missing runtime profile schema: {schema}")

    profiles_dir = skill_dir / "runtime-profiles"
    if not profiles_dir.exists():
        errors.append(f"Missing runtime profile directory: {profiles_dir}")
        return False, errors

    for profile in load_profiles(skill_dir):
        errors.extend(validate_profile_shape(profile))
        adapter_path = adapter_path_for(profile, skill_dir)
        if not adapter_path.exists():
            errors.append(f"{profile.path.name}: missing adapter reference {adapter_path.name}")

    return not errors, errors


def match_profile(profiles: list[RuntimeProfile], name: str) -> RuntimeProfile:
    needle = name.strip().lower()
    for profile in profiles:
        if profile.stem.lower() == needle or profile.runtime_name.lower() == needle:
            return profile
    raise ValueError(f"Unknown runtime profile '{name}'")


def supports_minimum(actual: str, required: str, order: dict[str, int]) -> bool:
    return order[actual] >= order[required]


def profile_matches(profile: RuntimeProfile, args: argparse.Namespace) -> bool:
    caps = profile.capabilities
    if args.support_level and not supports_minimum(profile.support_level, args.support_level, SUPPORT_LEVEL_ORDER):
        return False
    if args.require_structured_choice and not supports_minimum(
        caps["structured_choice"], args.require_structured_choice, STRUCTURED_CHOICE_ORDER
    ):
        return False
    if args.require_file_read_write and not supports_minimum(
        caps["file_read_write"], args.require_file_read_write, FILE_MODE_ORDER
    ):
        return False
    if args.require_subprocess and not caps["subprocess"]:
        return False
    if args.require_local_html and caps["local_html"] == "none":
        return False
    if args.require_file_presentation and caps["file_presentation"] == "none":
        return False
    if args.require_pause_resume and not caps["pause_resume"]:
        return False
    if args.require_long_term_memory and not caps["long_term_memory"]:
        return False
    if args.verifier in {"external_tool", "hybrid"} and not caps["subprocess"]:
        return False
    if args.verifier == "human_gate" and not caps["pause_resume"]:
        return False
    if args.verifier == "llm_judge" and not caps["freeform_input"]:
        return False
    return True


def render_summary(profile: RuntimeProfile) -> str:
    caps = profile.capabilities
    lines = [
        f"runtime: {profile.runtime_name}",
        f"profile: {profile.stem}",
        f"support_level: {profile.support_level}",
        "capabilities:",
        f"  structured_choice: {caps['structured_choice']}",
        f"  freeform_input: {str(caps['freeform_input']).lower()}",
        f"  file_presentation: {caps['file_presentation']}",
        f"  local_html: {caps['local_html']}",
        f"  subprocess: {str(caps['subprocess']).lower()}",
        f"  pause_resume: {str(caps['pause_resume']).lower()}",
        f"  file_read_write: {caps['file_read_write']}",
        f"  long_term_memory: {str(caps['long_term_memory']).lower()}",
    ]
    if profile.data["downgrades"]:
        lines.append("downgrades:")
        for item in profile.data["downgrades"]:
            lines.append(f"  - {item['capability']}: {item['effect']}")
    else:
        lines.append("downgrades: none")
    return "\n".join(lines)


def summarize_requirements(args: argparse.Namespace) -> tuple[list[str], list[str]]:
    requirements: list[str] = []
    blockers: list[str] = []
    if args.require_structured_choice:
        requirements.append(f"structured_choice>={args.require_structured_choice}")
    if args.require_file_read_write:
        requirements.append(f"file_read_write>={args.require_file_read_write}")
    if args.require_subprocess:
        requirements.append("subprocess")
    if args.require_local_html:
        requirements.append("local_html")
    if args.require_file_presentation:
        requirements.append("file_presentation")
    if args.require_pause_resume:
        requirements.append("pause_resume")
    if args.require_long_term_memory:
        requirements.append("long_term_memory")
    if args.verifier:
        requirements.append(f"verifier:{args.verifier}")
    return requirements, blockers


def mission_compatibility_issues(profile: RuntimeProfile, args: argparse.Namespace) -> list[str]:
    caps = profile.capabilities
    issues: list[str] = []
    if args.require_structured_choice and not supports_minimum(
        caps["structured_choice"], args.require_structured_choice, STRUCTURED_CHOICE_ORDER
    ):
        issues.append(
            f"requires structured_choice>={args.require_structured_choice}, but runtime provides {caps['structured_choice']}"
        )
    if args.require_file_read_write and not supports_minimum(
        caps["file_read_write"], args.require_file_read_write, FILE_MODE_ORDER
    ):
        issues.append(
            f"requires file_read_write>={args.require_file_read_write}, but runtime provides {caps['file_read_write']}"
        )
    if args.require_subprocess and not caps["subprocess"]:
        issues.append("requires subprocess execution, but runtime does not provide it")
    if args.require_local_html and caps["local_html"] == "none":
        issues.append("requires local HTML presentation, but runtime does not provide it")
    if args.require_file_presentation and caps["file_presentation"] == "none":
        issues.append("requires file presentation, but runtime does not provide it")
    if args.require_pause_resume and not caps["pause_resume"]:
        issues.append("requires pause/resume, but runtime does not provide it")
    if args.require_long_term_memory and not caps["long_term_memory"]:
        issues.append("requires long-term memory, but runtime does not provide it")
    if args.verifier == "external_tool" and not caps["subprocess"]:
        issues.append("external_tool verifiers require subprocess execution")
    if args.verifier == "hybrid" and not caps["subprocess"]:
        issues.append("hybrid verifiers with tool components require subprocess execution")
    if args.verifier == "human_gate" and not caps["pause_resume"]:
        issues.append("human_gate verifiers require pause/resume")
    if args.verifier == "llm_judge" and not caps["freeform_input"]:
        issues.append("llm_judge configuration requires freeform input")
    return issues


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect and select a* runtime profiles")
    parser.add_argument(
        "--skill-dir",
        default=str(default_skill_dir()),
        help="Path to the autostar-skill directory (default: inferred from script location)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List available runtime profiles")

    show = subparsers.add_parser("show", help="Show one runtime profile")
    show.add_argument("runtime", help="Runtime profile name or stem")

    validate = subparsers.add_parser("validate", help="Validate runtime profiles and adapter references")
    validate.add_argument("--quiet", action="store_true", help="Only emit validation failures")

    select = subparsers.add_parser("select", help="Select the best runtime for a capability set")
    select.add_argument("--support-level", choices=["full", "reduced", "unsupported"])
    select.add_argument("--require-structured-choice", choices=["basic", "full"])
    select.add_argument("--require-file-read-write", choices=["limited", "full"])
    select.add_argument("--require-subprocess", action="store_true")
    select.add_argument("--require-local-html", action="store_true")
    select.add_argument("--require-file-presentation", action="store_true")
    select.add_argument("--require-pause-resume", action="store_true")
    select.add_argument("--require-long-term-memory", action="store_true")
    select.add_argument("--verifier", choices=["deterministic", "external_tool", "llm_judge", "hybrid", "human_gate"])

    check = subparsers.add_parser(
        "check-mission",
        help="Check whether a specific runtime can support the current mission requirements",
    )
    check.add_argument("runtime", help="Runtime profile name or stem")
    check.add_argument("--require-structured-choice", choices=["basic", "full"], default="basic")
    check.add_argument("--require-file-read-write", choices=["limited", "full"], default="full")
    check.add_argument("--require-subprocess", action="store_true")
    check.add_argument("--require-local-html", action="store_true")
    check.add_argument("--require-file-presentation", action="store_true")
    check.add_argument("--require-pause-resume", action="store_true", default=True)
    check.add_argument("--require-long-term-memory", action="store_true")
    check.add_argument(
        "--verifier",
        action="append",
        choices=["deterministic", "external_tool", "llm_judge", "hybrid", "human_gate"],
        default=[],
        help="Verifier types needed by the mission. Repeatable.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    skill_dir = Path(args.skill_dir).resolve()

    if args.command == "validate":
        ok, errors = validate_profiles(skill_dir)
        if not ok:
            for error in errors:
                print(f"FAIL: {error}")
            return 1
        if not args.quiet:
            for profile in load_profiles(skill_dir):
                print(f"OK: {profile.path.name}")
        return 0

    profiles = load_profiles(skill_dir)

    if args.command == "list":
        for profile in profiles:
            print(f"{profile.stem}\t{profile.runtime_name}\t{profile.support_level}")
        return 0

    if args.command == "show":
        try:
            profile = match_profile(profiles, args.runtime)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 1
        print(render_summary(profile))
        return 0

    if args.command == "select":
        matches = [profile for profile in real_profiles(profiles) if profile_matches(profile, args)]
        if not matches:
            print("No runtime profile satisfies the requested capabilities.", file=sys.stderr)
            return 1
        matches.sort(
            key=lambda profile: (
                SUPPORT_LEVEL_ORDER[profile.support_level],
                STRUCTURED_CHOICE_ORDER[profile.capabilities["structured_choice"]],
                FILE_MODE_ORDER[profile.capabilities["file_read_write"]],
                int(profile.capabilities["subprocess"]),
                int(profile.capabilities["local_html"] != "none"),
            ),
            reverse=True,
        )
        print(render_summary(matches[0]))
        return 0

    if args.command == "check-mission":
        try:
            profile = match_profile(profiles, args.runtime)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 1

        base_args = argparse.Namespace(
            require_structured_choice=args.require_structured_choice,
            require_file_read_write=args.require_file_read_write,
            require_subprocess=args.require_subprocess,
            require_local_html=args.require_local_html,
            require_file_presentation=args.require_file_presentation,
            require_pause_resume=True,
            require_long_term_memory=args.require_long_term_memory,
            verifier=None,
        )
        issues = mission_compatibility_issues(profile, base_args)
        for verifier in args.verifier:
            verifier_ns = vars(base_args).copy()
            verifier_ns["verifier"] = verifier
            verifier_args = argparse.Namespace(**verifier_ns)
            issues.extend(mission_compatibility_issues(profile, verifier_args))
        issues = list(dict.fromkeys(issues))

        requirements, _ = summarize_requirements(base_args)
        requirements.extend(f"verifier:{verifier}" for verifier in args.verifier)

        if issues:
            print(f"runtime: {profile.runtime_name}")
            print(f"profile: {profile.stem}")
            print("mission_compatible: false")
            print("requirements:")
            for requirement in requirements:
                print(f"  - {requirement}")
            print("issues:")
            for issue in issues:
                print(f"  - {issue}")
            return 1

        print(f"runtime: {profile.runtime_name}")
        print(f"profile: {profile.stem}")
        print("mission_compatible: true")
        print("requirements:")
        for requirement in requirements:
            print(f"  - {requirement}")
        print("issues: none")
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
