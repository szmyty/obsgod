#!/usr/bin/env python3
"""Build and check the offline site at five mobile/Deck/desktop viewports.

Uses the repository's existing Playwright installation and an explicit Chromium
path. The loopback preview makes no external requests. Results are browser
evidence only; real Deck/controller, hosted-site and payment checks are separate.
"""
import argparse
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
import threading
import traceback
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
VIEWPORTS = (("mobile", 390, 844), ("small-mobile", 320, 780),
             ("deck", 1280, 800), ("deck-portrait", 800, 1280), ("desktop", 1440, 1000))
FUNDING = ("https://github.com/sponsors/szmyty", "https://www.buymeacoffee.com/szmyty",
           "https://ko-fi.com/szmyty", "https://opencollective.com/szmyty",
           "https://thanks.dev/u/gh/szmyty")


def output_directory(value):
    path = Path(value).absolute()
    if path.is_symlink():
        raise ValueError("Generated directories cannot be symlinks")
    resolved = path.resolve()
    if resolved.is_relative_to(ROOT) and not resolved.is_relative_to(ROOT / "dist"):
        raise ValueError("Use dist/ or directories outside the repository for generated files")
    return path


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def run_matrix(site, output, screenshots, executable):
    results, errors, remote, image_files = [], [], [], []
    manifest = json.loads((site / "site-manifest.json").read_text())
    proof = {"status": "failed", "source": manifest["source"], "cases": results,
             "console_errors": errors, "external_requests": remote,
             "python": platform.python_version(), "playwright": importlib.metadata.version("playwright"),
             "browser_executable": str(executable), "screenshots": {},
             "limitations": "Chromium viewport/offline navigation only; no real Deck/controller, hosted-site, payment or wallet acceptance."}
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(site)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"

    def watch(page, *, file_mode=False):
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)

        def route_request(route):
            url = route.request.url
            parsed = urlsplit(url)
            local = parsed.scheme == "http" and parsed.netloc == f"127.0.0.1:{server.server_port}"
            if local or parsed.scheme == "data" or (file_mode and parsed.scheme == "file"):
                route.continue_()
            else:
                remote.append(url)
                route.abort()
        page.route("**/*", route_request)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, executable_path=str(executable), args=["--no-sandbox"])
            proof["browser_version"] = browser.version
            try:
                for label, width, height in VIEWPORTS:
                    context = browser.new_context(viewport={"width": width, "height": height}, reduced_motion="reduce")
                    try:
                        page = context.new_page()
                        watch(page)
                        for path in sorted(site.glob("*.html")):
                            response = page.goto(f"{origin}/{path.name}", wait_until="load")
                            assert response and response.status == 200, (label, path.name, "missing page")
                            assert page.locator("main").count() == 1
                            assert page.locator("h1").count() == 1
                            assert page.locator("html").get_attribute("lang") == "en"
                            assert page.locator('nav [aria-current="page"]').count() == 1
                            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (label, path.name, "horizontal overflow")
                            assert tuple(page.locator(".support-actions a").evaluate_all("nodes => nodes.map(node => node.href)")) == FUNDING
                            assert page.locator(".wallet").count() == 0, "Default unconfigured wallets must stay hidden"
                            page.keyboard.press("Tab")
                            assert page.evaluate("document.activeElement.textContent") == "Skip to content"
                            page.evaluate("document.activeElement.blur()")
                            screenshot = None
                            if path.name == "index.html" and label != "small-mobile":
                                screenshot = screenshots / f"landing-{label}.png"
                            elif path.name == "configuration.html" and label == "mobile":
                                screenshot = screenshots / "configuration-mobile.png"
                            if screenshot:
                                page.screenshot(path=str(screenshot), full_page=True)
                                image_files.append(screenshot)
                            results.append({"viewport": label, "width": width, "height": height,
                                            "page": path.name, "status": "passed"})
                    finally:
                        context.close()
                context = browser.new_context(viewport={"width": 1280, "height": 800})
                try:
                    page = context.new_page()
                    watch(page, file_mode=True)
                    try:
                        page.goto((site / "index.html").as_uri(), wait_until="load")
                        assert page.locator("h1").inner_text() == "Your game.\nYour stream.\nYour Deck."
                        assert page.locator("body").evaluate("node => getComputedStyle(node).backgroundColor") == "rgb(11, 17, 27)"
                        page.get_by_role("link", name="Start with the setup guide").click()
                        assert page.url.endswith("/install.html")
                        assert page.get_by_role("heading", name="Install, check, then stream.").is_visible()
                        results.append({"mode": "file-offline", "navigation": "landing to install", "styles": "loaded", "status": "passed"})
                    except Exception as error:
                        if "ERR_BLOCKED_BY_ADMINISTRATOR" not in str(error):
                            raise
                        results.append({"mode": "file-offline", "status": "unavailable",
                                        "reason": "Managed Chromium policy blocks file:// navigation; offline loopback HTTP is checked separately."})
                finally:
                    context.close()
                assert not errors, errors
                assert not remote, remote
                proof["status"] = "passed-with-explicit-unavailable" if results[-1]["status"] == "unavailable" else "passed"
            finally:
                browser.close()
    except Exception as error:
        proof["failure"] = str(error)
        traceback.print_exc()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        proof["screenshots"] = {image.name: hashlib.sha256(image.read_bytes()).hexdigest() for image in image_files}
        (output / "matrix.json").write_text(json.dumps(proof, indent=2) + "\n")
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", type=Path, default=Path("/usr/bin/chromium"))
    parser.add_argument("--site-dir", type=Path, default=ROOT / "dist/site",
                        help="HTML build destination, rebuilt from the current source")
    parser.add_argument("--output", type=Path, default=ROOT / "dist/site-tests/browser",
                        help="JSON report directory")
    parser.add_argument("--screenshots", type=Path, help="PNG directory; defaults to OUTPUT/screenshots")
    args = parser.parse_args()
    try:
        site = output_directory(args.site_dir)
        output = output_directory(args.output)
        screenshots = output_directory(args.screenshots or output / "screenshots")
        if output.resolve().is_relative_to(site.resolve()) or screenshots.resolve().is_relative_to(site.resolve()):
            raise ValueError("Keep reports/screenshots outside the HTML build directory")
    except ValueError as error:
        parser.error(str(error))
    output.mkdir(parents=True, exist_ok=True)
    screenshots.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/build-site.py"), "--output", str(site)], cwd=ROOT, check=True)
    proof = run_matrix(site, output, screenshots, args.browser)
    count = sum("viewport" in item for item in proof["cases"])
    print(json.dumps({"status": proof["status"], "page_viewport_cases": count,
                      "console_errors": len(proof["console_errors"]), "external_requests": len(proof["external_requests"]),
                      "report": str(output / "matrix.json")}))
    return 0 if proof["status"].startswith("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
