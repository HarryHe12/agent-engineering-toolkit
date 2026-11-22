"""Check that distributed skill instructions have no missing local dependencies."""
import argparse
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


def check_package(root):
    root = Path(root).resolve()
    skills = sorted((root / "skills").glob("*/SKILL.md"))
    errors = []
    if not skills:
        errors.append("No skills/*/SKILL.md files found")
    for skill in skills:
        text = skill.read_text(encoding="utf-8")
        for raw in re.findall(r"\]\(([^)]+)\)", text):
            target = raw.strip().strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or not parsed.path:
                continue
            relative = unquote(parsed.path)
            resolved = (skill.parent / relative).resolve()
            if not resolved.is_relative_to(root):
                errors.append(f"{skill.relative_to(root)}: outside package: {target}")
            elif not resolved.is_file():
                errors.append(f"{skill.relative_to(root)}: missing: {target}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path,
                        default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = check_package(args.root)
    for error in errors:
        print(error)
    if errors:
        raise SystemExit(1)
    print("Skill package local dependencies: PASS")


if __name__ == "__main__":
    main()
