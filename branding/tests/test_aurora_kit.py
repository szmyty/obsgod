#!/usr/bin/env python3
"""Selected-aurora source, safety, ownership and ordinary-download contracts.

Set AURORA_TEST_REPOSITORY to exercise a complete private staged repository.
Set AURORA_TEST_RASTER=1 for the single pinned-tool raster/export integration
case. Pure SVG/source cases need only Python's standard library.
"""
import base64
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
import zlib


ROOT = Path(os.environ.get("AURORA_TEST_REPOSITORY", Path(__file__).resolve().parents[2])).resolve()
spec = importlib.util.spec_from_file_location("aurora_kit_under_test", ROOT / "scripts/generate-aurora-kit.py")
kit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = kit
spec.loader.exec_module(kit)

SVG = "http://www.w3.org/2000/svg"
SELECTED = Path(".identity/candidates/aurora")
REFERENCES = (
    ".identity/candidates/concepts/orbital-stream-color-alternatives.png",
    ".identity/candidates/concepts/orbital-stream-board.png",
    ".identity/candidates/concepts/orbital-stream-gradient-icon.png",
)


def sha(content):
    return hashlib.sha256(content).hexdigest()


def inventory(path):
    return {file.relative_to(path).as_posix(): (sha(file.read_bytes()), file.stat().st_mode & 0o777)
            for file in path.rglob("*") if file.is_file()}


def local_tag(node):
    return node.tag.rsplit("}", 1)[-1]


def page_fills(content):
    """Find a whole-page rect, rather than mistaking the light inset for one."""
    document = ET.fromstring(content)
    width, height = map(float, document.attrib["viewBox"].split()[-2:])
    fills = []
    for node in document.iter():
        if local_tag(node) != "rect":
            continue
        try:
            covers = (float(node.get("x", "0")) == 0 and float(node.get("y", "0")) == 0 and
                      float(node.get("width", "0")) >= width and float(node.get("height", "0")) >= height)
        except ValueError:
            covers = False
        if covers:
            fills.append(node.get("fill"))
    return fills


def png(content):
    """Independently validate complete PNG chunks, CRCs and compressed rows."""
    if content[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError("Not an ordinary PNG")
    offset, compressed, header, seen_end = 8, bytearray(), None, False
    while offset < len(content):
        if len(content) - offset < 12:
            raise AssertionError("Truncated PNG chunk")
        size = struct.unpack(">I", content[offset:offset + 4])[0]
        kind = content[offset + 4:offset + 8]
        end = offset + 8 + size
        if end + 4 > len(content):
            raise AssertionError("Truncated PNG payload")
        payload = content[offset + 8:end]
        expected_crc = struct.unpack(">I", content[end:end + 4])[0]
        if zlib.crc32(kind + payload) & 0xffffffff != expected_crc:
            raise AssertionError("PNG CRC mismatch")
        if kind == b"IHDR":
            if offset != 8 or header is not None or size != 13:
                raise AssertionError("Invalid PNG header placement")
            header = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            if size or end + 4 != len(content):
                raise AssertionError("PNG trailing data or nonempty IEND")
            seen_end = True
        offset = end + 4
    if header is None or not seen_end or not compressed:
        raise AssertionError("Incomplete PNG")
    width, height, depth, color, compression, filtering, interlace = header
    if not width or not height or compression or filtering or interlace:
        raise AssertionError("Expected normal noninterlaced PNG export")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color)
    if channels is None or depth not in (1, 2, 4, 8, 16):
        raise AssertionError("Unsupported PNG format")
    row_bytes = math.ceil(width * channels * depth / 8)
    rows = zlib.decompress(bytes(compressed))
    if len(rows) != height * (row_bytes + 1):
        raise AssertionError("PNG decompressed dimensions differ")
    if any(rows[index] > 4 for index in range(0, len(rows), row_bytes + 1)):
        raise AssertionError("Invalid PNG row filter")
    return width, height


class Gallery(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images, self.external, self.active = [], [], []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag in {"script", "iframe", "object", "embed"}:
            self.active.append(tag)
        if tag == "img":
            self.images.append(attrs.get("src", ""))
        for name in ("src", "href"):
            value = attrs.get(name, "")
            if value and not value.startswith(("data:image/png;base64,", "#")):
                self.external.append(value)


class AuroraKit(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="aurora-kit-contract-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.source_count = 0

    def copy_source(self):
        self.source_count += 1
        root = self.base / ("source-" + str(self.source_count))
        paths = set(kit.INPUT_PATHS) | {
            ".identity/governance/approvals.json", ".identity/governance/provenance.json"}
        for relative in paths:
            source, target = ROOT / relative, root / relative
            self.assertTrue(source.is_file(), relative)
            self.assertFalse(source.is_symlink(), relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        return root

    def put_local_asset(self, root, name, content):
        path = root / SELECTED / name
        path.write_bytes(content)
        manifest_path = root / SELECTED / "inventory.json"
        value = json.loads(manifest_path.read_text())
        matched = [entry for entry in value["assets"] if entry["path"] == path.relative_to(root).as_posix()]
        self.assertEqual(len(matched), 1, name)
        matched[0]["sha256"] = sha(content)
        manifest_path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")

    def mutate_geometry(self, root, name):
        document = ET.fromstring((root / SELECTED / name).read_bytes())
        path = document.find(".//{" + SVG + "}path")
        self.assertIsNotNone(path, name)
        path.set("transform", "translate(1 0)")
        self.put_local_asset(root, name, ET.tostring(document, encoding="utf-8"))

    def test_repeatable_candidate_outputs_do_not_invent_approval(self):
        files = kit.render()
        self.assertEqual(files, kit.render())
        manifest = json.loads(files[kit.MANIFEST])
        self.assertEqual(manifest["profile"], kit.PROFILE)
        self.assertEqual(manifest["approval"], "proposed-unapproved")
        candidate = json.loads((ROOT / SELECTED / "inventory.json").read_text())
        self.assertEqual(candidate["profile"], kit.PROFILE)
        self.assertTrue(candidate["assets"])
        self.assertTrue(all(entry.get("humanApproval") is None for entry in candidate["assets"]))
        self.assertEqual(json.loads((ROOT / ".identity/governance/approvals.json").read_text())["decisions"], [])
        self.assertEqual(json.loads((ROOT / ".identity/governance/provenance.json").read_text())["assets"], [])

    def test_main_geometry_reaches_the_real_main_surfaces(self):
        root = self.copy_source()
        before = kit.render(root)
        self.mutate_geometry(root, "mark.svg")
        after = kit.render(root)
        for surface in ("masters/mark.svg", "masters/mark-transparent.svg", "masters/mark-on-light.svg",
                        "docs/wordmark.svg", "github/readme-header-light.svg",
                        "github/social-preview.svg"):
            self.assertNotEqual(before[surface], after[surface], surface)
        self.assertEqual(before["masters/mark-small.svg"], after["masters/mark-small.svg"])
        # The atmospheric header deliberately projects the separately recorded
        # raster master; editing vector geometry must not pretend to edit it.
        self.assertEqual(before["github/readme-header.svg"], after["github/readme-header.svg"])

    def test_compact_source_is_independent_and_reaches_actual_size_review(self):
        root = self.copy_source()
        before = kit.render(root)
        self.mutate_geometry(root, "mark-small.svg")
        after = kit.render(root)
        for surface in ("masters/mark-small.svg", "review/legibility-sheet.svg", "review/menu-sheet.svg"):
            self.assertNotEqual(before[surface], after[surface], surface)
        self.assertEqual(before["masters/mark-transparent.svg"], after["masters/mark-transparent.svg"])

    def test_unrelated_identity_files_are_not_hidden_render_inputs(self):
        root = self.copy_source()
        before = kit.render(root)
        unrelated = root / ".identity/candidates/unrelated-note.txt"
        unrelated.parent.mkdir(parents=True, exist_ok=True)
        unrelated.write_text("This is not selected artwork or an input.\n")
        after = kit.render(root)
        self.assertEqual(before, after)
        self.assertNotIn(unrelated.relative_to(root).as_posix(), json.loads(after[kit.MANIFEST])["sources"])

    def test_reference_digest_mismatch_is_not_silently_adopted(self):
        root = self.copy_source()
        path = root / REFERENCES[0]
        content = bytearray(path.read_bytes())
        content[-1] ^= 1
        path.write_bytes(content)
        with self.assertRaises(ValueError):
            kit.render(root)

    def test_a_different_palette_selection_is_not_aurora_authorization(self):
        root = self.copy_source()
        path = root / ".identity/candidates/concepts/selection.json"
        selection = json.loads(path.read_text())
        selection["selectedPrimary"]["variantNumber"] = "02"
        selection["selectedPrimary"]["variantName"] = "afterglow"
        path.write_text(json.dumps(selection) + "\n")
        with self.assertRaises(ValueError):
            kit.render(root)

    def test_active_or_external_svg_is_rejected_even_with_matching_local_digest(self):
        def with_element(document, tag, attributes=None):
            child = ET.SubElement(document, "{" + SVG + "}" + tag, attributes or {})
            child.text = "fixture"

        def event(document):
            document.set("onload", "alert('fixture')")

        def remote_paint(document):
            document.find(".//{" + SVG + "}path").set("fill", "url(https://example.invalid/paint.svg#x)")

        def escaped_remote_paint(document):
            document.find(".//{" + SVG + "}path").set(
                "fill", r"u\72l(//127.0.0.1:54321/paint.svg#gradient)")

        mutations = {
            "script": lambda document: with_element(document, "script"),
            "foreign-object": lambda document: with_element(document, "foreignObject"),
            "remote-image": lambda document: with_element(document, "image", {"href": "https://example.invalid/x.png"}),
            "event": event,
            "remote-paint": remote_paint,
            "css-escaped-remote-paint": escaped_remote_paint,
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                root = self.copy_source()
                document = ET.fromstring((root / SELECTED / "mark.svg").read_bytes())
                mutate(document)
                self.put_local_asset(root, "mark.svg", ET.tostring(document, encoding="utf-8"))
                with self.assertRaises(ValueError):
                    kit.render(root)

    def test_stylesheet_processing_instruction_is_rejected_even_with_matching_digest(self):
        root = self.copy_source()
        source = (root / SELECTED / "mark.svg").read_bytes()
        instruction = b'<?xml-stylesheet type="text/css" href="https://example.invalid/fixture.css"?>\n'
        # Updating the declared local digest makes this reach the SVG policy;
        # a digest mismatch would not exercise the external stylesheet gap.
        self.put_local_asset(root, "mark.svg", instruction + source)
        with self.assertRaises(ValueError):
            kit.render(root)

    def test_foreign_svg_namespaces_and_attributes_are_rejected(self):
        foreign = "urn:aurora-test:foreign"

        def foreign_node(document):
            ET.SubElement(document, "{" + foreign + "}rect", {"width": "1", "height": "1", "fill": "#ffffff"})

        def foreign_attribute(document):
            document.find(".//{" + SVG + "}path").set("{" + foreign + "}fill", "#ffffff")

        def foreign_root(document):
            document.tag = "{" + foreign + "}svg"

        for name, mutate in (("element", foreign_node), ("attribute", foreign_attribute), ("root", foreign_root)):
            with self.subTest(name=name):
                root = self.copy_source()
                document = ET.fromstring((root / SELECTED / "mark.svg").read_bytes())
                mutate(document)
                self.put_local_asset(root, "mark.svg", ET.tostring(document, encoding="utf-8"))
                with self.assertRaises(ValueError):
                    kit.render(root)

    def test_selected_surfaces_retain_gradient_and_distinct_background_treatments(self):
        files = kit.render()
        colors = json.loads((ROOT / SELECTED / "palette.json").read_text())["colors"]
        self.assertIn(colors["ink"], page_fills(files["masters/mark.svg"]))
        self.assertIn(colors["light"], page_fills(files["masters/mark-on-light.svg"]))
        self.assertEqual(page_fills(files["masters/mark-transparent.svg"]), [])
        self.assertEqual(page_fills(files["masters/mark-small.svg"]), [])
        for surface in ("masters/mark-transparent.svg", "masters/mark-on-light.svg"):
            document = ET.fromstring(files[surface])
            self.assertTrue(any(local_tag(node) == "linearGradient" for node in document.iter()), surface)
            self.assertTrue(any("url(#" in value for node in document.iter() for value in node.attrib.values()), surface)
        wordmark = ET.fromstring(files["docs/wordmark.svg"])
        visible_text = " ".join("".join(node.itertext()) for node in wordmark.iter() if local_tag(node) == "text")
        self.assertIn("deckystream", visible_text)
        self.assertNotIn("Decky Stream", visible_text)

    def test_review_text_palette_has_independent_normal_text_contrast(self):
        colors = json.loads((ROOT / SELECTED / "palette.json").read_text())["colors"]

        def luminance(value):
            channels = [int(value[index:index + 2], 16) / 255 for index in (1, 3, 5)]
            linear = [channel / 12.92 if channel <= .04045 else ((channel + .055) / 1.055) ** 2.4
                      for channel in channels]
            return sum(channel * weight for channel, weight in zip(linear, (.2126, .7152, .0722)))

        for foreground, background in (("text", "ink"), ("muted", "ink"), ("lightText", "light")):
            high, low = sorted((luminance(colors[foreground]), luminance(colors[background])), reverse=True)
            self.assertGreaterEqual((high + .05) / (low + .05), 4.5, foreground + " on " + background)

    def test_ordinary_foreign_output_is_preserved(self):
        output = self.base / "output"
        output.mkdir()
        protected = output / "owner-note.txt"
        protected.write_text("preserve owner data\n")
        before = inventory(output)
        with self.assertRaises(ValueError):
            kit.write_or_check(kit.render(), output)
        self.assertEqual(inventory(output), before)

    def test_old_mint_output_is_not_owned_by_the_aurora_profile(self):
        output = self.base / "old-mint"
        shutil.copytree(ROOT / "branding/repository", output)
        before = inventory(output)
        self.assertIn("draft-manifest.json", before)
        with self.assertRaises(ValueError):
            kit.write_or_check(kit.render(), output)
        self.assertEqual(inventory(output), before)

    def test_profile_mismatch_cannot_claim_another_generated_tree(self):
        output, files = self.base / "output", kit.render()
        kit.write_or_check(files, output)
        manifest_path = output / kit.MANIFEST
        manifest = json.loads(manifest_path.read_text())
        manifest["profile"] = "mint-signal"
        manifest_path.write_text(json.dumps(manifest) + "\n")
        before = inventory(output)
        with self.assertRaises(ValueError):
            kit.write_or_check(files, output)
        self.assertEqual(inventory(output), before)

    def test_output_path_traversal_is_rejected_without_modifying_destination(self):
        protected = self.base / "protected"
        protected.mkdir()
        (protected / "owner.txt").write_text("preserve\n")
        (self.base / "box").mkdir()
        output = self.base / "box" / ".." / "protected"
        before = inventory(protected)
        with self.assertRaises(ValueError):
            kit.write_or_check(kit.render(), output)
        self.assertEqual(inventory(protected), before)

    def test_output_symlink_ancestry_is_preserved(self):
        protected = self.base / "protected"
        protected.mkdir()
        (protected / "owner.txt").write_text("preserve\n")
        link = self.base / "alias"
        link.symlink_to(protected, target_is_directory=True)
        before = inventory(protected)
        with self.assertRaises(ValueError):
            kit.write_or_check(kit.render(), link / "new-output")
        self.assertTrue(link.is_symlink())
        self.assertEqual(inventory(protected), before)

    def test_owned_output_symlink_is_preserved(self):
        output, files = self.base / "output", kit.render()
        kit.write_or_check(files, output)
        protected = self.base / "owner.svg"
        protected.write_text("preserve\n")
        target = output / "masters/mark.svg"
        target.unlink()
        target.symlink_to(protected)
        with self.assertRaises(ValueError):
            kit.write_or_check(files, output)
        self.assertTrue(target.is_symlink())
        self.assertEqual(protected.read_text(), "preserve\n")

    def test_owned_output_and_manifest_hardlinks_cannot_overwrite_outside_files(self):
        for relative in ("masters/mark.svg", kit.MANIFEST):
            with self.subTest(path=relative):
                root = self.copy_source()
                output = root / "branding/aurora"
                original_files = kit.render(root)
                kit.write_or_check(original_files, output)
                target = output / relative
                outside = self.base / ("outside-owner-" + str(self.source_count))
                os.link(target, outside)
                before_bytes = outside.read_bytes()
                before_identity = (outside.stat().st_dev, outside.stat().st_ino)
                before_output = inventory(output)
                self.assertEqual(target.stat().st_nlink, 2)
                # A legitimate new source version changes both the mark and
                # manifest. Reject every unsafe preimage before any replacement;
                # otherwise a late manifest refusal could leave a partial tree.
                self.mutate_geometry(root, "mark.svg")
                replacement = kit.render(root)
                self.assertNotEqual(original_files[relative], replacement[relative])
                with self.assertRaises(ValueError):
                    kit.write_or_check(replacement, output)
                self.assertEqual(outside.read_bytes(), before_bytes)
                self.assertEqual((outside.stat().st_dev, outside.stat().st_ino), before_identity)
                self.assertTrue(os.path.samefile(target, outside))
                self.assertEqual(target.stat().st_nlink, 2)
                self.assertEqual(inventory(output), before_output)

    def test_source_symlink_is_rejected_without_modifying_the_target(self):
        root = self.copy_source()
        source = root / SELECTED / "mark.svg"
        protected = self.base / "owner.svg"
        protected.write_bytes(source.read_bytes())
        expected = protected.read_bytes()
        source.unlink()
        source.symlink_to(protected)
        with self.assertRaises(ValueError):
            kit.render(root)
        self.assertTrue(source.is_symlink())
        self.assertEqual(protected.read_bytes(), expected)

    def test_drift_check_never_repairs_modified_output(self):
        output, files = self.base / "output", kit.render()
        kit.write_or_check(files, output)
        path = output / "docs/wordmark.svg"
        path.write_bytes(path.read_bytes() + b"\n<!-- deliberate drift -->\n")
        before = inventory(output)
        with self.assertRaises(ValueError):
            kit.write_or_check(files, output, check=True)
        self.assertEqual(inventory(output), before)

    def test_selected_generation_preserves_references_mint_and_governance(self):
        root = self.copy_source()
        shutil.copytree(ROOT / "branding/repository", root / "branding/repository")
        mint_before = inventory(root / "branding/repository")
        self.assertGreaterEqual(len(mint_before), 31)
        retained = (*REFERENCES, ".identity/governance/approvals.json", ".identity/governance/provenance.json")
        before = {path: (root / path).read_bytes() for path in retained}
        files = kit.render(root)
        kit.write_or_check(files, root / "branding/aurora")
        kit.write_or_check(files, root / "branding/aurora", check=True)
        self.assertEqual(inventory(root / "branding/repository"), mint_before)
        self.assertEqual({path: (root / path).read_bytes() for path in retained}, before)

    @unittest.skipUnless(os.environ.get("AURORA_TEST_RASTER") == "1",
                         "Set AURORA_TEST_RASTER=1 to execute the pinned-tool raster/export integration case")
    def test_pinned_raster_exports_are_ordinary_decodable_downloads_with_an_offline_gallery(self):
        files = kit.render(raster=True)
        required = {
            "web/favicon-16.png": (16, 16), "web/favicon-24.png": (24, 24),
            "web/favicon-32.png": (32, 32), "web/favicon-64.png": (64, 64),
            "github/avatar-256.png": (256, 256), "github/avatar-512.png": (512, 512),
            "github/social-preview.png": (1280, 640),
            "github/readme-header.png": (1600, 600), "github/readme-header-light.png": (1600, 600),
            "masters/mark-transparent.png": (512, 512), "masters/mark-on-light.png": (512, 512),
        }
        png_files = {path: content for path, content in files.items() if path.endswith(".png")}
        for path, dimensions in required.items():
            self.assertIn(path, files)
            self.assertEqual(png(files[path]), dimensions, path)
        for path, content in png_files.items():
            with self.subTest(path=path):
                png(content)
        self.assertLessEqual(len(files["github/social-preview.png"]), 999999)
        gallery = Gallery()
        gallery.feed(files["index.html"].decode())
        self.assertEqual(gallery.external, [])
        self.assertEqual(gallery.active, [])
        self.assertEqual(len(gallery.images), len(png_files))
        expected = {sha(content) for content in png_files.values()}
        for image in gallery.images:
            self.assertTrue(image.startswith("data:image/png;base64,"))
            content = base64.b64decode(image.split(",", 1)[1], validate=True)
            self.assertIn(sha(content), expected)
            png(content)
        archives = [content for path, content in files.items() if path == "deckystream-aurora-png.zip"]
        self.assertEqual(len(archives), 1)
        with zipfile.ZipFile(io.BytesIO(archives[0])) as archive:
            self.assertIsNone(archive.testzip())
            names = archive.namelist()
            self.assertTrue(any(name.endswith("START-HERE.txt") for name in names))
            self.assertTrue(all(Path(name).suffix in {".png", ".txt"} for name in names))
            self.assertEqual(len({str(Path(name).parent) for name in names}), 1)
            for info in archive.infolist():
                self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual(info.external_attr >> 16, 0o100644)
                if info.filename.endswith(".png"):
                    data = archive.read(info)
                    self.assertIn(sha(data), expected)
                    png(data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
