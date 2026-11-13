#!/usr/bin/env python3
"""Meaningful draft input/output ownership, drift and source projection checks."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("brand_kit", ROOT / "scripts/generate-brand-kit.py")
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)


class BrandKit(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)

    def copy_source(self):
        root = self.base / "source"
        for path in (".identity", "branding/licenses", "scripts"):
            (root / path).mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT / ".identity", root / ".identity", dirs_exist_ok=True)
        shutil.copytree(ROOT / "branding/licenses", root / "branding/licenses", dirs_exist_ok=True)
        shutil.copyfile(ROOT / "scripts/generate-brand-kit.py", root / "scripts/generate-brand-kit.py")
        return root

    def test_identical_sources_yield_identical_archive(self):
        self.assertEqual(kit.render(), kit.render())

    def test_candidates_remain_unapproved(self):
        files = kit.render()
        manifest = json.loads(files[kit.MANIFEST])
        self.assertEqual(manifest["approval"], "proposed-unapproved")
        self.assertEqual(json.loads((ROOT / ".identity/governance/approvals.json").read_text())["decisions"], [])
        self.assertIn(b"humanApproval", files["metadata/rights-and-sources.json"])

    def test_master_changes_project_into_every_geometry_surface(self):
        root = self.copy_source()
        before = kit.render(root)
        path = root / ".identity/candidates/mark.svg"
        path.write_text(path.read_text().replace("M40 32", "M41 32"))
        after = kit.render(root)
        for surface in ("masters/mark.svg", "docs/wordmark.svg", "github/social-preview.svg", "review/legibility-sheet.svg"):
            self.assertNotEqual(before[surface], after[surface], surface)

    def test_active_svg_is_rejected(self):
        root = self.copy_source()
        path = root / ".identity/candidates/mark.svg"
        path.write_text(path.read_text().replace("</svg>", "<script>alert(1)</script></svg>"))
        with self.assertRaises(ValueError):
            kit.render(root)

    def test_foreign_file_is_preserved(self):
        output = self.base / "output"
        output.mkdir()
        protected = output / "other.txt"
        protected.write_text("preserve")
        with self.assertRaises(ValueError):
            kit.write_or_check(kit.render(), output)
        self.assertEqual(protected.read_text(), "preserve")

    def test_output_symlink_is_preserved(self):
        output, protected = self.base / "output", self.base / "protected"
        output.mkdir()
        protected.write_text("preserve")
        (output / "masters").symlink_to(self.base)
        with self.assertRaises(ValueError):
            kit.write_or_check(kit.render(), output)
        self.assertEqual(protected.read_text(), "preserve")

    def test_drift_check_refuses_modified_export_without_writing(self):
        output, files = self.base / "output", kit.render()
        kit.write_or_check(files, output)
        changed = output / "docs/wordmark.svg"
        changed.write_text("drift")
        with self.assertRaises(ValueError):
            kit.write_or_check(files, output, check=True)
        self.assertEqual(changed.read_text(), "drift")

    def test_a_new_human_decision_requires_the_approved_pipeline(self):
        root = self.copy_source()
        path = root / ".identity/governance/approvals.json"
        value = json.loads(path.read_text())
        value["decisions"] = [{"id": "fixture"}]
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            kit.render(root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
