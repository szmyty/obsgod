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
import decky
import install as installer
from product import DISPLAY_NAME

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
        result = {"running": False, "ok": False, "message": "OBS/capture installation failed. Check Discover, disk space and your connection, then retry."}
        try:
            installer.ensure_dependencies()
            result = {"running": False, "ok": True, "message": "Compatible OBS with bundled WebSocket support and its capture plugin are installed. Save your settings below."}
        except (OSError, RuntimeError, subprocess.SubprocessError):
            pass
        with self.job_lock:
            self.job = result

    def install_plugin(self):
        with self.job_lock:
            if self.job["running"]:
                return dict(self.job)
            self.job = {"running": True, "message": "Checking output, preserving your settings and installing OBSGod through Decky…"}
        threading.Thread(target=self.finish_plugin_install, daemon=True).start()
        return dict(self.job)

    def finish_plugin_install(self):
        try:
            installer.install(launch=False)
            result = {"running": False, "ok": True, "message": "The OBSGod app and Decky plugin are installed and verified. Return to Gaming Mode to make a local clip before streaming."}
        except RuntimeError as error:
            result = {"running": False, "ok": False, "message": str(error)}
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            result = {"running": False, "ok": False, "message": "Installation could not be verified. Keep Steam/Decky open in Desktop Mode and rerun the complete installer. Your settings were not reset."}
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
            result["decky_status"] = decky.status()
            result["decky"] = result["decky_status"]["ok"]
            result["plugin_zip"] = str(ROOT / "obsgod-decky.zip")
            result["product_name"] = DISPLAY_NAME
            self.send_data(200, result)
        elif path == "/api/connection":
            self.send_data(200, run_cli("connection-info", timeout=5))
        elif path == "/api/stream-health":
            self.send_data(200, run_cli("stream-health", timeout=6))
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
            elif action == "install-plugin":
                self.send_data(200, self.server.install_plugin())
            elif action == "configure":
                settings = request.get("settings")
                if not isinstance(settings, dict):
                    raise ValueError()
                self.send_data(200, run_cli("configure", settings))
            elif action in {"stream-profiles", "set-idle-media", "media"}:
                settings = request.get("settings")
                if not isinstance(settings, dict):
                    raise ValueError()
                self.send_data(200, run_cli(action, settings))
            elif action == "stream-health":
                self.send_data(200, run_cli(action, timeout=6))
            elif action == "retry-recovery":
                self.send_data(200, run_cli(action, timeout=18))
            elif action == "change-obs-password":
                settings = request.get("settings")
                if not isinstance(settings, dict):
                    raise ValueError()
                self.send_data(200, run_cli(action, settings, timeout=7))
            elif action == "test-connection":
                self.send_data(200, run_cli(action, timeout=5))
            elif action in {"doctor", "stop", "restart", "open-obs"}:
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
