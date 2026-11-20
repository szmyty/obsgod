import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("aurora_ui", ROOT / "scripts/generate-aurora-ui.py")
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)


class AuroraProjection(unittest.TestCase):
    def test_local_selected_vector_roundtrips_without_external_resources(self):
        raw = (ROOT / ".identity/candidates/aurora/mark-small.svg").read_bytes()
        self.assertEqual(unquote(ui.icon_data(raw).split(",", 1)[1]).encode(), raw)

    def test_active_referenced_and_rebased_svg_cannot_enter_the_bundle(self):
        prefix = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"'
        for raw in [
            prefix + '><script>unexpected()</script></svg>',
            prefix + '><image href="https://example.invalid/image.png"/></svg>',
            prefix + ' xml:base="https://example.invalid/"><path fill="url(#local)"/></svg>',
            prefix + '><path fill="url(https://example.invalid/paint)"/></svg>',
            prefix + '><path fill="url(#missing)"/></svg>',
            prefix + '><path fill="u\\72l(//example.invalid/paint.svg#gradient)"/></svg>',
            '<?xml-stylesheet href="https://example.invalid/style"?>' + prefix + '></svg>',
            '<!DOCTYPE svg [<!ENTITY source SYSTEM "file:///private">]>' + prefix + '></svg>',
        ]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                ui.icon_data(raw.encode())

    def test_non_png_or_unbounded_dimensions_cannot_enter_the_site(self):
        with self.assertRaises(ValueError):
            ui.png(b"<svg/>")
        raw = bytearray((ROOT / "branding/aurora/web/favicon-32.png").read_bytes())
        raw[16:20] = (100_000).to_bytes(4, "big")
        with self.assertRaises(ValueError):
            ui.png(raw)

    def test_linked_sources_are_not_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.write_text("preserve")
            link = Path(directory) / "linked"
            link.symlink_to(source)
            with self.assertRaises(ValueError):
                ui.regular(link)
            self.assertEqual(source.read_text(), "preserve")

    def test_missing_outputs_do_not_follow_a_linked_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            outside = Path(directory) / "outside"
            outside.mkdir()
            (root / "site").mkdir(parents=True)
            (root / "site/assets").symlink_to(outside, target_is_directory=True)
            with patch.object(ui, "ROOT", root), patch("sys.argv", ["generate-aurora-ui.py"]):
                with self.assertRaises(ValueError):
                    ui.main()
            self.assertFalse((outside / "brand-icon.png").exists())

    def test_hardlinked_output_cannot_overwrite_unrelated_owner_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            output = root / "steamdeck/decky/src/aurora-brand.mjs"
            output.parent.mkdir(parents=True)
            owner = Path(directory) / "owner.txt"
            owner.write_text("preserve")
            os.link(owner, output)
            with patch.object(ui, "ROOT", root), patch("sys.argv", ["generate-aurora-ui.py"]):
                with self.assertRaises(ValueError):
                    ui.main()
            self.assertEqual(owner.read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
