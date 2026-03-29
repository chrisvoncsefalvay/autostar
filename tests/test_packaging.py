from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_package_targets_build_claude_code_and_claude_ai_archives(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "autostar-skill/scripts/package_skill.py",
            "--target",
            "all",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert (tmp_path / "autostar-skill.skill").exists()
    assert (tmp_path / "autostar-claude-ai-skill.zip").exists()

