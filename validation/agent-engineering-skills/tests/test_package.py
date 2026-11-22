"""Distribution contracts, independent of skill wording or workflow ordering."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.build_package import build_package
from tools.check_package import check_package


class PackageContracts(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.skill = self.root / "skills" / "example" / "SKILL.md"
        self.skill.parent.mkdir(parents=True)
        self.skill.write_text("")

    def test_bundled_reference_and_external_url_are_valid(self):
        (self.skill.parent / "details.md").write_text("Details")
        self.skill.write_text("[local](details.md#part) [web](https://example.com)")
        self.assertEqual(check_package(self.root), [])

    def test_missing_sibling_dependency_is_rejected(self):
        self.skill.write_text("[governance](../unbundled/SKILL.md)")
        self.assertEqual(len(check_package(self.root)), 1)

    def test_reference_outside_distribution_is_rejected(self):
        self.skill.write_text("[outside](../../../outside.md)")
        self.assertEqual(len(check_package(self.root)), 1)

    def test_encoded_local_filename_is_supported(self):
        (self.skill.parent / "feature map.md").write_text("Map")
        self.skill.write_text("[map](feature%20map.md)")
        self.assertEqual(check_package(self.root), [])

    def test_empty_package_is_rejected(self):
        self.skill.unlink()
        self.assertEqual(len(check_package(self.root)), 1)

    def test_actual_distribution_is_self_contained(self):
        root = Path(__file__).resolve().parents[1]
        archive = self.root / "release.zip"
        manifest = build_package(root, archive)
        self.assertEqual(len(manifest), 3)
        extracted = self.root / "unpacked"
        with zipfile.ZipFile(archive) as package:
            package.extractall(extracted)
        self.assertEqual(check_package(extracted), [])

    def test_manifest_hashes_match_distributed_bytes(self):
        import hashlib
        root = Path(__file__).resolve().parents[1]
        archive = self.root / "release.zip"
        manifest = build_package(root, archive)
        with zipfile.ZipFile(archive) as package:
            for name, digest in manifest.items():
                self.assertEqual(hashlib.sha256(package.read(name)).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
