"""Verified local Decky helper boundary; no tokens, settings or stderr are exposed."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
OFFICIAL_DECKY = "https://decky.xyz/"


def helper_request(operation, package=ROOT, manifest=None, uninstall_existing=False):
    if operation not in {"probe", "install", "uninstall"}:
        raise RuntimeError("Unknown Decky operation")
    helper = ROOT / "decky-install"
    if helper.is_symlink() or not helper.is_file():
        raise RuntimeError("The verified Decky installer is missing. Extract the complete OBSGod release and retry.")
    helper.chmod(0o700)
    request = {"operation": operation}
    if uninstall_existing:
        if operation != "uninstall":
            raise RuntimeError("Existing plugin removal is only valid for uninstall")
        request["uninstall_existing"] = True
    temporary = None
    if operation == "install":
        if not manifest or not re.fullmatch(r"[0-9][A-Za-z0-9.-]{0,79}", manifest.get("version", "")):
            raise RuntimeError("The plugin package version is invalid")
        source = package / "obsgod-decky.zip"
        expected = manifest.get("files", {}).get("obsgod-decky.zip")
        if source.is_symlink() or not source.is_file() or not re.fullmatch(r"[a-f0-9]{64}", expected or ""):
            raise RuntimeError("The verified Decky ZIP is missing")
        data = source.read_bytes()
        if len(data) > 32 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError("The Decky ZIP checksum does not match the release")
        # The Go boundary requires private regular ZIPs. Never chmod or mutate a
        # previous installed release while a running process may still use it.
        temporary = tempfile.TemporaryDirectory(prefix="obsgod-decky-")
        private_zip = Path(temporary.name) / "obsgod-decky.zip"
        private_zip.write_bytes(data)
        private_zip.chmod(0o600)
        request.update(zip_path=str(private_zip), sha256=expected, version=manifest["version"])
    try:
        process = subprocess.run([str(helper)], input=json.dumps(request), capture_output=True, text=True, timeout=100 if operation in {"install", "uninstall"} else 25)
        result = json.loads(process.stdout)
        if not isinstance(result, dict) or not isinstance(result.get("ok"), bool) or (result.get("ok") and process.returncode != 0):
            raise ValueError()
        if not result["ok"]:
            message = result.get("message")
            if not isinstance(message, str) or len(message) > 600 or any(c in message for c in "\r\x00"):
                raise ValueError()
            raise RuntimeError(message)
        if operation == "install" and result.get("version") != manifest["version"]:
            raise RuntimeError("Decky did not confirm the requested OBSGod version. Rerun this installer to repair both copies.")
        if operation == "uninstall" and result.get("removed") is not True:
            raise RuntimeError("Decky did not confirm plugin removal. Inspect Decky before deleting application files.")
        return result
    except (OSError, subprocess.SubprocessError, ValueError):
        raise RuntimeError("Decky's installer could not be verified. Keep Steam and Decky running in Desktop Mode, check the visible installer log and retry. Your saved settings were preserved.") from None
    finally:
        if temporary is not None:
            temporary.cleanup()


def status():
    try:
        result = helper_request("probe")
        return {"ok": True, "running": True, "frontend_connected": result.get("frontend_connected") is True, "version": result.get("decky_version", "unknown"), "message": "Decky service and Steam connection are ready."}
    except RuntimeError as error:
        return {"ok": False, "running": False, "frontend_connected": False, "version": "unknown", "message": str(error) + " Official Decky installation: " + OFFICIAL_DECKY}
