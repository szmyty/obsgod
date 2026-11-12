#!/usr/bin/env python3
"""Exercise site determinism and unsafe-input/output failures using real fixtures.

Run directly for the production build plus safety cases and a JSON report:
    python3 site/tests/test_build.py --output dist/site-tests/build
The cases also work with unittest discovery. No network or new dependency is used.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("decky_stream_site_builder", ROOT / "scripts/build-site.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def output_directory(value):
    """Keep generated QA files out of versioned inputs."""
    path = Path(value).absolute()
    if path.is_symlink():
        raise ValueError("The QA output cannot be a symlink")
    resolved = path.resolve()
    if resolved.is_relative_to(ROOT) and not resolved.is_relative_to(ROOT / "dist"):
        raise ValueError("Use dist/ or a directory outside the repository for QA output")
    return path


class BuildSiteSafety(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="decky-stream-site-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.source = self.base / "source"
        for directory in ("site", "scripts", "steamdeck/decky/src", ".github"):
            (self.source / directory).mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT / "site", self.source / "site", dirs_exist_ok=True)
        for name in ("product.json", "support.json", ".github/FUNDING.yml",
                     "steamdeck/decky/src/support-data.mjs", "scripts/build-site.py"):
            shutil.copyfile(ROOT / name, self.source / name)

    def render(self):
        return builder.render(self.source)[0]

    def test_identical_inputs_produce_identical_bytes(self):
        self.assertEqual(self.render(), self.render())

    def test_python_bytecode_cache_does_not_change_outputs(self):
        first = self.render()
        cache = self.source / "site/tests/__pycache__"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "test_build.cpython-312.pyc").write_bytes(b"interpreter-cache-fixture")
        (self.source / "site/leftover.pyc").write_bytes(b"other-interpreter-cache-fixture")
        self.assertEqual(first, self.render())

    def test_display_metadata_is_html_escaped(self):
        path = self.source / "product.json"
        product = json.loads(path.read_text())
        product["display_name"] = '<script>alert("injection")</script>'
        path.write_text(json.dumps(product))
        rendered = self.render()["index.html"]
        self.assertIn(b"&lt;script&gt;", rendered)
        self.assertNotIn(b"<script>alert", rendered)

    def test_invalid_repository_is_rejected(self):
        path = self.source / "product.json"
        product = json.loads(path.read_text())
        product["repository"] = "szmyty/obsgod?redirect=elsewhere"
        path.write_text(json.dumps(product))
        with self.assertRaises(ValueError):
            self.render()

    def test_non_https_support_url_is_rejected(self):
        path = self.source / "steamdeck/decky/src/support-data.mjs"
        raw = path.read_text()
        support = json.loads(raw[len(builder.GENERATED_PREFIX):-2])
        support["providers"][0]["url"] = "javascript:alert(1)"
        path.write_text(builder.GENERATED_PREFIX + json.dumps(support) + ";\n")
        with self.assertRaises(ValueError):
            self.render()

    def test_remote_css_import_is_rejected(self):
        css = self.source / "site/assets/site.css"
        css.write_text(css.read_text() + '\n@import "https://example.invalid/style.css";')
        with self.assertRaises(ValueError):
            self.render()

    def test_symlink_output_refuses_without_modifying_target(self):
        output = self.base / "output"
        output.mkdir()
        protected = self.base / "protected"
        protected.write_text("preserve")
        (output / "index.html").symlink_to(protected)
        with self.assertRaises(ValueError):
            builder.write_or_check(self.render(), output)
        self.assertEqual(protected.read_text(), "preserve")

    def test_unrelated_output_is_preserved(self):
        output = self.base / "output"
        output.mkdir()
        protected = output / "unrelated.txt"
        protected.write_text("preserve")
        with self.assertRaises(ValueError):
            builder.write_or_check(self.render(), output)
        self.assertEqual(protected.read_text(), "preserve")

    def test_stale_output_check_is_rejected(self):
        output = self.base / "output"
        files = self.render()
        builder.write_or_check(files, output)
        builder.write_or_check(files, output, check=True)
        (output / "index.html").write_text("stale")
        with self.assertRaises(ValueError):
            builder.write_or_check(files, output, check=True)

    def test_broken_local_link_is_rejected(self):
        files = self.render()
        original = files["index.html"]
        files["index.html"] = original.replace(b'href="install.html"', b'href="missing.html"', 1)
        self.assertNotEqual(files["index.html"], original, "The link fixture no longer matches the landing page")
        with self.assertRaises(ValueError):
            builder.check_links(files)

    def test_broken_local_anchor_is_rejected(self):
        files = self.render()
        original = files["index.html"]
        files["index.html"] = original.replace(b"configuration.html#capture", b"configuration.html#missing", 1)
        self.assertNotEqual(files["index.html"], original, "The anchor fixture no longer matches the landing page")
        with self.assertRaises(ValueError):
            builder.check_links(files)


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed_cases = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed_cases.append(test.id())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/site-tests/build",
                        help="Generated preview/report directory; use dist/ or a location outside the repo")
    args = parser.parse_args()
    try:
        output = output_directory(args.output)
    except ValueError as error:
        parser.error(str(error))
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/build-site.py"),
                    "--output", str(output / "preview")], cwd=ROOT, check=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BuildSiteSafety)
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
    manifest = json.loads((output / "preview/site-manifest.json").read_text())
    proof = {"status": "passed" if result.wasSuccessful() else "failed",
             "source": manifest["source"], "case_count": result.testsRun,
             "passed_cases": result.passed_cases,
             "failed_cases": [test.id() for test, _ in result.failures],
             "error_cases": [test.id() for test, _ in result.errors],
             "skipped_cases": [{"test": test.id(), "reason": reason} for test, reason in result.skipped],
             "scope": "Site build/fixture checks only; no device, hosting or publication qualification."}
    (output / "safety.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"status": proof["status"], "case_count": result.testsRun,
                      "report": str(output / "safety.json")}))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
