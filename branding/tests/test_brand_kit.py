#!/usr/bin/env python3
"""Meaningful draft input/output ownership, drift and source projection checks."""
import importlib.util
import base64
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

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
        document = ET.fromstring(path.read_bytes())
        first_path = document.find("{http://www.w3.org/2000/svg}path")
        self.assertIsNotNone(first_path)
        first_path.set("transform", "translate(1 0)")
        path.write_bytes(ET.tostring(document))
        after = kit.render(root)
        for surface in ("masters/mark.svg", "masters/mark-transparent.svg", "masters/mark-on-light.svg",
                        "docs/wordmark.svg", "github/social-preview.svg", "github/readme-header.svg",
                        "github/readme-header-light.svg", "review/legibility-sheet.svg"):
            self.assertNotEqual(before[surface], after[surface], surface)

    def test_repository_projection_retains_sources_and_only_its_owned_outputs(self):
        full = kit.render()
        projected = kit.repository_assets(full)
        manifest = json.loads(projected[kit.MANIFEST])
        self.assertEqual(manifest["approval"], "proposed-unapproved")
        self.assertEqual(manifest["sources"], json.loads(full[kit.MANIFEST])["sources"])
        self.assertEqual(set(manifest["outputs"]), set(projected) - {kit.MANIFEST})
        self.assertEqual(projected["header.svg"], full["github/readme-header.svg"])
        self.assertEqual(projected["icon-monochrome.svg"], full["decky/icon-monochrome.svg"])
        self.assertNotIn("decky-stream-proposed.zip", projected)
        output = self.base / "repository"
        kit.write_or_check(projected, output)
        kit.write_or_check(projected, output, check=True)
        foreign = output / "hand-authored.svg"
        foreign.write_text("preserve")
        with self.assertRaises(ValueError):
            kit.write_or_check(projected, output)
        self.assertEqual(foreign.read_text(), "preserve")

    def test_gallery_embeds_viewable_images_without_network_or_script(self):
        png = (ROOT / "branding/repository/favicon-32.png").read_bytes()
        gallery = kit.preview_gallery({"web/favicon-32.png": png, "tokens/colors.json": b"{}"})
        class References(HTMLParser):
            def __init__(self):
                super().__init__()
                self.images, self.external, self.scripts = [], [], []
            def handle_starttag(self, tag, attributes):
                attrs = dict(attributes)
                if tag == "img":
                    self.images.append(attrs["src"])
                if tag == "script":
                    self.scripts.append(attrs)
                for name in ("src", "href"):
                    value = attrs.get(name, "")
                    if value and not value.startswith("data:image/png;base64,"):
                        self.external.append(value)
        parser = References()
        parser.feed(gallery.decode())
        self.assertEqual(len(parser.images), 1)
        self.assertEqual(base64.b64decode(parser.images[0].split(",", 1)[1]), png)
        self.assertEqual(parser.external, [])
        self.assertEqual(parser.scripts, [])
        self.assertIn(b"JSON / CSS", gallery)
        self.assertIn(b"SVG", gallery)

    def test_easy_archive_is_flat_normal_pngs_and_plain_text_with_valid_crc(self):
        png = (ROOT / "branding/repository/favicon-32.png").read_bytes()
        files = {"web/favicon-32.png": png, "github/header.png": png, "metadata/source.json": b"{}"}
        archive = kit.png_previews(files)
        self.assertEqual(archive, kit.png_previews(files))
        with zipfile.ZipFile(io.BytesIO(archive)) as reader:
            self.assertIsNone(reader.testzip())
            self.assertEqual(sorted(reader.namelist()), [
                "decky-stream-png-previews/START-HERE.txt",
                "decky-stream-png-previews/favicon-32.png",
                "decky-stream-png-previews/header.png",
            ])
            self.assertEqual(reader.read("decky-stream-png-previews/favicon-32.png"), png)
            for info in reader.infolist():
                self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual(info.external_attr >> 16, 0o100644)

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
