import json
import unittest

from tests._fakes import REPO_ROOT  # noqa: F401  (path setup)


class ExtensionManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        manifest_path = REPO_ROOT / "extension" / "manifest.json"
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    def test_manifest_v3(self) -> None:
        self.assertEqual(self.manifest["manifest_version"], 3)

    def test_side_panel_default_path(self) -> None:
        self.assertEqual(self.manifest["side_panel"]["default_path"], "sidepanel.html")

    def test_required_permissions_present(self) -> None:
        permissions = set(self.manifest.get("permissions", []))
        for required in ("sidePanel", "storage", "scripting", "tabs"):
            self.assertIn(required, permissions, f"missing permission: {required}")

    def test_host_permissions_include_all_urls(self) -> None:
        self.assertIn("<all_urls>", self.manifest.get("host_permissions", []))

    def test_background_service_worker(self) -> None:
        self.assertEqual(self.manifest["background"]["service_worker"], "background.js")

    def test_version_bumped(self) -> None:
        self.assertEqual(self.manifest["version"], "0.2.0")


if __name__ == "__main__":
    unittest.main()
