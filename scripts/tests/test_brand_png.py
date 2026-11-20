import importlib.util
from pathlib import Path
import struct
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("brand_png_test", ROOT / "scripts/brand_png.py")
png = importlib.util.module_from_spec(spec)
spec.loader.exec_module(png)


def chunk(kind, value):
    return struct.pack(">I", len(value)) + kind + value + struct.pack(">I", zlib.crc32(kind + value) & 0xffffffff)


def sample(rows=b"\0\x10\x20\x30\xff", color=6):
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, color, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


class PNGProfile(unittest.TestCase):
    def test_real_selected_exports_and_small_rgb_rgba_are_accepted_unchanged(self):
        for value in [sample(), sample(b"\0\x10\x20\x30", 2),
                      (ROOT / "branding/aurora/web/favicon-32.png").read_bytes(),
                      (ROOT / "branding/aurora/github/readme-header.png").read_bytes()]:
            self.assertEqual(png.validate_png(value), value)

    def test_truncated_bad_crc_invalid_rows_and_trailing_streams_are_rejected(self):
        original = sample()
        bad_crc = bytearray(original)
        bad_crc[-1] ^= 1
        for value in [original[:33], original[:-1], bytes(bad_crc), original + b"extra",
                      sample(b"\0\x10"), sample(b"\5\x10\x20\x30\xff"), sample(b"\0" * 1000)]:
            with self.subTest(size=len(value)), self.assertRaises(ValueError):
                png.validate_png(value)


if __name__ == "__main__":
    unittest.main()
