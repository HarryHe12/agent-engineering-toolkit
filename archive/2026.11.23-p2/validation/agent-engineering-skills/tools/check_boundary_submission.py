"""Exercise a submitted boundary checker against independent contract examples."""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


CASES = {
    "shared_dependency_allowed": (True, "from app.shared.labels import normalize_label\n", {}),
    "main_from_import_rejected": (False, "from app.main.disk import normalize_label\n", {}),
    "main_alias_import_rejected": (False, "import app.main.disk as disk\n", {}),
    "renderer_helper_rejected": (
        False, "from app.renderer.helper import normalize_label\n",
        {"app/renderer/helper.py": "from app.main.disk import normalize_label\n"},
    ),
    "shared_transitive_main_rejected": (
        False, "from app.shared.proxy import normalize_label\n",
        {"app/shared/proxy.py": "from app.main.disk import normalize_label\n"},
    ),
    "relative_main_import_rejected": (False, "from ..main.disk import normalize_label\n", {}),
    "main_internal_import_allowed": (
        True, "from app.shared.labels import normalize_label\n",
        {"app/main/internal.py": "import app.main.disk\n"},
    ),
    "empty_source_rejected": (False, None, {}),
}


def check_submission(source):
    results = []
    for name, (allowed, renderer, extras) in CASES.items():
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(source / "scripts", root / "scripts")
            if renderer is not None:
                shutil.copytree(source / "app", root / "app")
                (root / "app/renderer/view.py").write_text(renderer)
            for relative, content in extras.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            process = subprocess.run(
                [sys.executable, "scripts/check_boundaries.py"], cwd=root,
                text=True, capture_output=True, timeout=15,
            )
            output = (process.stdout + process.stderr).replace(str(root), "<workspace>")
            results.append({"case": name, "expected_allowed": allowed,
                            "exit_code": process.returncode,
                            "passed": (process.returncode == 0) == allowed,
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
