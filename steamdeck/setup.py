#!/usr/bin/env python3
"""Authenticated loopback-only setup. Credentials are entered on this device."""
import hmac
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import webbrowser

from bridge import private_process, run_cli

ROOT = Path(__file__).resolve().parent
MAX_BODY = 16384


class SetupServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address=("127.0.0.1", 0)):
        super().__init__(address, Handler)
        self.token = secrets.token_urlsafe(32)
        self.origin = "http://127.0.0.1:" + str(self.server_port)
        self.job_lock = threading.Lock()
        self.job = {"running": False, "message": ""}
        self.last_used = time.monotonic()

    def dependencies(self):
        with self.job_lock:
            if self.job["running"]:
                return dict(self.job)
            self.job = {"running": True, "message": "Installing OBS and the capture plugin in your home. This can take several minutes."}
        threading.Thread(target=self.install_dependencies, daemon=True).start()
        return dict(self.job)

    def install_dependencies(self):
        commands = [
            ["flatpak", "remote-add", "--user", "--if-not-exists", "flathub", "https://flathub.org/repo/flathub.flatpakrepo"],
            ["flatpak", "install", "--user", "--noninteractive", "-y", "flathub", "com.obsproject.Studio", "com.obsproject.Studio.Plugin.Gstreamer"],
        ]
        result = {"running": False, "ok": False, "message": "Flatpak installation failed. Check your connection, free disk space and Discover, then retry."}
        try:
            for command in commands:
                subprocess.run(command, check=True, timeout=1200, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            result = {"running": False, "ok": True, "message": "OBS and the GStreamer capture plugin are installed. Save your settings below."}
        except (OSError, subprocess.SubprocessError):
            pass
        with self.job_lock:
            self.job = result


class Handler(BaseHTTPRequestHandler):
    server_version = "OBSGodSetup"

    def log_message(self, *_):
        pass  # No HTTP URLs, request payloads or credentials enter logs.

    def send_data(self, status, payload, content_type="application/json"):
        data = json.dumps(payload).encode() if content_type == "application/json" else payload
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(data)

    def valid_host(self):
        return self.headers.get("Host") == "127.0.0.1:" + str(self.server.server_port)

    def authorized(self):
        authorization = self.headers.get("Authorization", "")
        origin = self.headers.get("Origin")
        return self.valid_host() and (origin is None or origin == self.server.origin) and hmac.compare_digest(authorization, "Bearer " + self.server.token)

    def do_GET(self):
        if not self.valid_host():
            self.send_data(403, {"ok": False})
            return
        path = urlsplit(self.path).path
        static = {"/": ("setup.html", "text/html; charset=utf-8"), "/setup.js": ("setup.js", "text/javascript; charset=utf-8"), "/setup.css": ("setup.css", "text/css; charset=utf-8")}
        if path in static:
            file, content_type = static[path]
            self.send_data(200, (ROOT / file).read_bytes(), content_type)
            return
        if not self.authorized():
            self.send_data(403, {"ok": False, "message": "Reopen OBSGod Setup from the application menu."})
            return
        self.server.last_used = time.monotonic()
        if path == "/api/status":
            result = run_cli("status", timeout=6)
            result["flatpak"] = shutil.which("flatpak") is not None
            result["decky"] = (Path.home() / "homebrew" / "plugins").is_dir()
            result["plugin_zip"] = str(ROOT / "obsgod-decky.zip")
            self.send_data(200, result)
        elif path == "/api/job":
            with self.server.job_lock:
                result = dict(self.server.job)
            self.send_data(200, result)
        else:
            self.send_data(404, {"ok": False})

    def do_POST(self):
        if not self.authorized():
            self.send_data(403, {"ok": False, "message": "Setup authorization expired. Reopen OBSGod Setup."})
            return
        self.server.last_used = time.monotonic()
        if urlsplit(self.path).path != "/api/action":
            self.send_data(404, {"ok": False})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError()
            request = json.loads(self.rfile.read(length))
            if not isinstance(request, dict):
                raise ValueError()
            action = request.get("action")
            if action == "dependencies":
                self.send_data(200, self.server.dependencies())
            elif action == "configure":
                settings = request.get("settings")
                if not isinstance(settings, dict):
                    raise ValueError()
                self.send_data(200, run_cli("configure", settings))
            elif action in {"doctor", "stop", "restart"}:
                self.send_data(200, run_cli(action))
            elif action == "close":
                self.send_data(200, {"ok": True, "message": "Setup closed. You can close this tab."})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                self.send_data(400, {"ok": False, "message": "Unknown setup action"})
        except (ValueError, TypeError, OSError):
            self.send_data(400, {"ok": False, "message": "Invalid setup request"})


def main():
    private_process()
    server = SetupServer()
    url = server.origin + "/#" + server.token
    # Some browser launchers wait for the first page to load before returning.
    # Serve first so those launchers cannot block their own HTTP response.
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.5}, daemon=True)
    thread.start()
    print("OBSGod Setup is running locally. Keep this terminal open until you finish setup.", flush=True)
    print("If the browser does not open, open this link on this Deck:", flush=True)
    print(url, flush=True)
    try:
        try:
            if not webbrowser.open(url):
                print("Automatic browser launch was unavailable. Use the local link above.", flush=True)
        except (webbrowser.Error, OSError):
            print("Automatic browser launch failed. Use the local link above.", flush=True)
        while thread.is_alive():
            thread.join(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


if __name__ == "__main__":
    main()
