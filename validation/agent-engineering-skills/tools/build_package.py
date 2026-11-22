"""Build standard SKILL.md directories from the reviewed distribution sources."""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path


def build_package(root, output):
    root = Path(root)
    sources = sorted((root / "skill-sources").glob("*.stage"))
    if not sources:
        raise ValueError("No reviewed skill sources found")
    entries = {}
    for source in sources:
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", source.stem):
            raise ValueError(f"Invalid skill name: {source.stem}")
        entries[f"skills/{source.stem}/SKILL.md"] = source.read_bytes()
    manifest = {name: hashlib.sha256(data).hexdigest()
                for name, data in entries.items()}
    entries["MANIFEST.json"] = json.dumps(manifest, indent=2).encode() + b"\n"
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = build_package(Path(__file__).resolve().parents[1], args.output)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
