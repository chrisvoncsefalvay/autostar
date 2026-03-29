#!/usr/bin/env python3
"""
Skill packager for Claude Code `.skill` archives and Claude.ai upload `.zip` archives.
"""

import argparse
import fnmatch
import sys
import zipfile
from pathlib import Path

try:
    from scripts.quick_validate import validate_skill
except ModuleNotFoundError:
    # Support direct execution via `python autostar-skill/scripts/package_skill.py`.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from quick_validate import validate_skill

# Patterns to exclude when packaging skills.
EXCLUDE_DIRS = {"__pycache__", "node_modules"}
EXCLUDE_GLOBS = {"*.pyc"}
EXCLUDE_FILES = {".DS_Store"}
# Directories excluded only at the skill root (not when nested deeper).
ROOT_EXCLUDE_DIRS = {"evals"}
PACKAGE_TARGETS = {
    "claude-code": {
        "path": "autostar-skill",
        "extension": ".skill",
    },
    "claude-ai": {
        "path": "autostar-claude-ai-skill",
        "extension": ".zip",
    },
}


def should_exclude(rel_path: Path) -> bool:
    """Check if a path should be excluded from packaging."""
    parts = rel_path.parts
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    # rel_path is relative to skill_path.parent, so parts[0] is the skill
    # folder name and parts[1] (if present) is the first subdir.
    if len(parts) > 1 and parts[1] in ROOT_EXCLUDE_DIRS:
        return True
    name = rel_path.name
    if name in EXCLUDE_FILES:
        return True
    return any(fnmatch.fnmatch(name, pat) for pat in EXCLUDE_GLOBS)


def package_skill(skill_path, output_dir=None, extension=".skill", archive_name=None):
    """
    Package a skill folder into a .skill file.

    Args:
        skill_path: Path to the skill folder
        output_dir: Optional output directory for the .skill file (defaults to current directory)

    Returns:
        Path to the created .skill file, or None if error
    """
    skill_path = Path(skill_path).resolve()

    # Validate skill folder exists
    if not skill_path.exists():
        print(f"Error: Skill folder not found: {skill_path}")
        return None

    if not skill_path.is_dir():
        print(f"Error: Path is not a directory: {skill_path}")
        return None

    # Validate SKILL.md exists
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        print(f"Error: SKILL.md not found in {skill_path}")
        return None

    # Run validation before packaging
    print("Validating skill...")
    valid, message = validate_skill(skill_path)
    if not valid:
        print(f"Validation failed: {message}")
        print("   Please fix the validation errors before packaging.")
        return None
    print(f"{message}\n")

    # Determine output location
    skill_name = skill_path.name
    if output_dir:
        output_path = Path(output_dir).resolve()
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path = Path.cwd()

    skill_filename = output_path / (archive_name or f"{skill_name}{extension}")

    # Create the .skill file (zip format)
    try:
        with zipfile.ZipFile(skill_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Walk through the skill directory, excluding build artifacts
            for file_path in skill_path.rglob('*'):
                if not file_path.is_file():
                    continue
                arcname = file_path.relative_to(skill_path.parent)
                if should_exclude(arcname):
                    print(f"  Skipped: {arcname}")
                    continue
                zipf.write(file_path, arcname)
                print(f"  Added: {arcname}")

        print(f"\nSuccessfully packaged skill to: {skill_filename}")
        return skill_filename

    except Exception as e:
        print(f"Error creating .skill file: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Package autostar skill artifacts")
    parser.add_argument("skill_path", nargs="?", help="Path to a skill directory")
    parser.add_argument("output_dir", nargs="?", help="Output directory for the archive")
    parser.add_argument(
        "--target",
        choices=["claude-code", "claude-ai", "all"],
        help="Package a predefined target instead of a direct skill path",
    )
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[2]
    output_dir = args.output_dir
    results = []

    if args.target:
        if output_dir is None and args.skill_path:
            output_dir = args.skill_path
            args.skill_path = None
        targets = PACKAGE_TARGETS.keys() if args.target == "all" else (args.target,)
        for target in targets:
            config = PACKAGE_TARGETS[target]
            skill_path = repo / config["path"]
            print(f"Packaging target: {target} ({skill_path})")
            if output_dir:
                print(f"   Output directory: {output_dir}")
            print()
            result = package_skill(
                skill_path,
                output_dir,
                extension=config["extension"],
                archive_name=f"{skill_path.name}{config['extension']}",
            )
            results.append(result is not None)
    else:
        if not args.skill_path:
            parser.error("either skill_path or --target is required")
        print(f"Packaging skill: {args.skill_path}")
        if output_dir:
            print(f"   Output directory: {output_dir}")
        print()
        result = package_skill(args.skill_path, output_dir)
        results.append(result is not None)

    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
