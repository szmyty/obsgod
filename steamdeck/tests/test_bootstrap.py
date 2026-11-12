"""Exercise the desktop entry's process lifecycle instead of bypassing it."""
import hashlib
import json
import os
from pathlib import Path
import select
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def previous_app_install_command(package):
    """Seed old app files; the transport fixture seeds/verifies plugins itself."""
    command = [sys.executable, str(package / "install.py"), "--no-launch"]
    manifest = json.loads((package / "manifest.json").read_text())
    if "decky.py" in manifest.get("files", {}):
        command.append("--app-only")
    return command


def desktop_command(path, as_uri=False):
    line = next(line[5:] for line in path.read_text().splitlines() if line.startswith("Exec="))
    return [
        (path.as_uri() if as_uri else str(path)) if value == "%k" else value for value in shlex.split(line)
    ]


def read_until(process, marker, timeout=10):
    output = bytearray()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ready, _, _ = select.select([process.stdout], [], [], 0.1)
        if ready:
            chunk = os.read(process.stdout.fileno(), 4096)
            if not chunk:
                break
            output.extend(chunk)
            if marker in output:
                return bytes(output)
    raise AssertionError("Launcher did not preserve the requested terminal output")


class DesktopBootstrap(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.package = self.base / "package with spaces %20"
        self.package.mkdir()
        self.home = self.base / "home"
        self.home.mkdir()
        for name in ["install.py", "Install OBSGod.desktop"]:
            shutil.copyfile(ROOT / name, self.package / name)
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"))

    def tearDown(self):
        self.temp.cleanup()

    def fake_payload(self):
        files = {"obsgod", "setup.py", "bridge.py", "setup.html", "setup.js", "setup.css", "uninstall.py", "obsgod-decky.zip", "LICENSE", "THIRD_PARTY_NOTICES.md", "STEAM-DECK.md"}
        for name in files:
            (self.package / name).write_text("fixture")
        (self.package / "setup.py").write_text("raise RuntimeError('visible setup startup failure')\n")
        (self.package / "manifest.json").write_text(json.dumps({"version": "0.1.0-bootstrap-test", "files": {name: hashlib.sha256((self.package / name).read_bytes()).hexdigest() for name in files}}))

    def launch(self, as_uri=False):
        return subprocess.Popen(desktop_command(self.package / "Install OBSGod.desktop", as_uri) + ["--app-only"], cwd=self.home,
                                env=self.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def finish(self, process):
        if process.poll() is None:
            process.communicate(b"\n", timeout=10)
        else:
            process.communicate()

    def test_failed_install_keeps_error_visible_until_enter(self):
        process = self.launch()
        try:
            output = read_until(process, b"Press Enter to close")
            self.assertIn(b"Extract the entire OBSGod archive", output)
            self.assertIsNone(process.poll())
        finally:
            self.finish(process)
        self.assertNotEqual(process.returncode, 0)

    def test_setup_crash_is_visible_for_path_and_file_uri(self):
        self.fake_payload()
        for as_uri in [False, True]:
            with self.subTest(as_uri=as_uri):
                process = self.launch(as_uri)
                try:
                    output = read_until(process, b"Press Enter to close")
                    self.assertIn(b"visible setup startup failure", output)
                    self.assertIn(b"Files were installed, but the setup page failed", output)
                    self.assertIsNone(process.poll())
                finally:
                    self.finish(process)
                self.assertNotEqual(process.returncode, 0)

    def test_server_serves_before_blocking_browser_launcher_returns(self):
        browser = self.base / "browser-probe"
        browser.write_text("#!" + sys.executable + "\n" + """
import json, sys, urllib.parse, urllib.request
url=urllib.parse.urlsplit(sys.argv[1])
base=urllib.parse.urlunsplit((url.scheme,url.netloc,'','',''))
with urllib.request.urlopen(base,timeout=3) as r:
 assert r.status==200
request=urllib.request.Request(base+'/api/action',data=b'{"action":"close"}',headers={'Authorization':'Bearer '+url.fragment,'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=3) as r:
 assert json.load(r)['ok']
""")
        browser.chmod(0o700)
        result = subprocess.run([sys.executable, str(ROOT / "setup.py")], env=dict(self.env, BROWSER=str(browser)), capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn(b"Automatic browser launch", result.stdout)


if __name__ == "__main__":
    unittest.main()
