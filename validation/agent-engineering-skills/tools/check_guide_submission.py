"""Rerun a reviewed CLI guide against healthy and deliberately broken products."""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def prepare_checkout(root):
    (root / "evidence").mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "add", "ledger.py"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=Fixture Author", "-c",
                    "user.email=fixture@example.invalid", "commit", "-qm",
                    "Record isolated product"], cwd=root, check=True)


def check_submission(source):
    guide = (source / "docs/verify-ledger.txt").read_text()
    match = re.search(r"python3 - <<'PY'\n(.*?)\nPY", guide, re.DOTALL)
    if not match:
        raise ValueError("Guide has no runnable Python heredoc")
    script = match.group(1)
    original = (source / "ledger.py").read_text()
    results = []
    for name, replacement in [("healthy", original),
                              ("trim_regression", original.replace(".strip()", ""))]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ledger.py").write_text(replacement)
            prepare_checkout(root)
            process = subprocess.run([sys.executable, "-c", script], cwd=root,
                                     text=True, capture_output=True, timeout=20)
            evidence = [p for p in root.rglob("*") if p.is_file()
                        and ".git" not in p.parts and p.name != "ledger.py"]
            output = (process.stdout + process.stderr).replace(str(root), "<workspace>")
            expected_success = name == "healthy"
            passed = ((process.returncode == 0) == expected_success) and bool(evidence)
            results.append({"case": name, "exit_code": process.returncode,
                            "evidence_survives": bool(evidence), "passed": passed,
                            "output": output})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    results = check_submission(args.source.resolve())
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if not all(row["passed"] for row in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
