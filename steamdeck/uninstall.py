#!/usr/bin/env python3
"""Remove OBSGod's installed application; preserve recordings and credentials by default."""
import argparse
import os
from pathlib import Path
import shutil
from bridge import run_cli


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--purge-settings", action="store_true", help="Also remove OBSGod credentials and its isolated OBS configuration")
    args = parser.parse_args()
    if os.getuid() == 0:
        raise SystemExit("Run without sudo")
    home = Path.home().resolve()
    base = home / ".local/share/obsgod"
    if base.is_symlink() or not base.resolve().is_relative_to(home):
        raise SystemExit("Unsafe installation path")
    state = run_cli("status", timeout=6)
    if state.get("stream", {}).get("active") or state.get("state") == "unknown":
        raise SystemExit("Stop streaming and inspect OBS first; the output is active or unconfirmed")
    if state.get("configured"):
        stopped = run_cli("restart", timeout=15)
        if not stopped.get("ok"):
            raise SystemExit(stopped.get("message", "Could not close idle OBS"))
    executable = home / ".local/bin/obsgod"
    if executable.is_symlink() and executable.readlink() == base / "current/obsgod":
        executable.unlink()
    desktop = home / ".local/share/applications/obsgod-setup.desktop"
    if desktop.is_file() and not desktop.is_symlink() and "X-OBSGod-Managed=true" in desktop.read_text():
        desktop.unlink()
    if args.purge_settings:
        config = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config"))) / "obsgod"
        obs = home / ".var/app/com.obsproject.Studio/config/obsgod"
        for path in [config, obs]:
            if path.is_symlink() or not path.resolve().is_relative_to(home):
                raise SystemExit("Refusing to remove settings outside the home directory")
            if path.is_dir():
                shutil.rmtree(path)
    if (base / "releases").is_dir() and not (base / "releases").is_symlink():
        shutil.rmtree(base / "releases")
    current = base / "current"
    if current.is_symlink():
        current.unlink()
    print("OBSGod removed. Recordings and executable backups are preserved.")
    print("Remove the OBSGod plugin through Decky as well. OBS / GStreamer remain installed.")


if __name__ == "__main__":
    main()
