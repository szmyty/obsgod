"""Shared Desktop paths. Existing installations keep their compatibility location."""
import os
from pathlib import Path


DEFAULTS = {
    "XDG_CONFIG_HOME": ".config",
    "XDG_DATA_HOME": ".local/share",
    "XDG_STATE_HOME": ".local/state",
    "XDG_CACHE_HOME": ".cache",
}


def xdg_root(name, home, environ=None):
    """Resolve one supported absolute XDG base; empty means the standard default."""
    values = os.environ if environ is None else environ
    value = values.get(name, "")
    if name not in DEFAULTS:
        raise ValueError("Unsupported XDG base directory")
    if not isinstance(value, str) or any(char in value for char in "\x00\r\n"):
        raise ValueError(name + " contains an unsupported path")
    root = Path(value) if value else Path(home) / DEFAULTS[name]
    if not root.is_absolute():
        raise ValueError(name + " must be an absolute directory")
    if ".." in root.parts:
        raise ValueError(name + " must not contain parent-directory traversal")
    return root


def validate_owned_root(path, home):
    """Validate a writable application root before creating any directories."""
    home_boundary = Path(home)
    home = home_boundary.resolve()
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or path.resolve() == home or not path.resolve().is_relative_to(home):
        raise ValueError("Application paths must stay inside your home directory")
    for item in [path, *path.parents]:
        if item in (home, home_boundary) or not item.resolve().is_relative_to(home):
            continue
        if item.is_symlink():
            raise ValueError("Refusing a symlinked application directory: " + str(item))
        if item.exists() and (not item.is_dir() or item.stat().st_uid != os.getuid()):
            raise ValueError("An application directory has unexpected type or ownership: " + str(item))


def app_directories(home, environ=None):
    """Return (app data, Desktop entries), preserving a pre-XDG install.

    No implicit data migration occurs when a user changes XDG_DATA_HOME. Two
    existing locations require a deliberate repair instead of guessing which
    installation owns the current OBS connection and updater state.
    """
    home = Path(home)
    data = xdg_root("XDG_DATA_HOME", home, environ)
    legacy = home / ".local/share/obsgod"
    wanted = data / "obsgod"
    if wanted != legacy and (legacy.exists() or legacy.is_symlink()):
        if wanted.exists() or wanted.is_symlink():
            raise ValueError("Two OBSGod installation locations exist. Resolve the XDG data migration before changing either installation.")
        return legacy, home / ".local/share/applications"
    return wanted, data / "applications"


def decky_locations(home, environ=None):
    """Resolve only the stable obsgod plugin's Decky roots, never shared parents."""
    values = os.environ if environ is None else environ
    root_value = values.get("DECKY_HOME", "")
    root = Path(root_value) if root_value else Path(home) / "homebrew"
    if not root.is_absolute() or ".." in root.parts or any(c in str(root) for c in "\x00\r\n") or not root.resolve().is_relative_to(Path(home).resolve()):
        raise ValueError("DECKY_HOME must identify a safe absolute directory inside your home")
    expected = {"plugin": root / "plugins/obsgod", "settings": root / "settings/obsgod",
                "data": root / "data/obsgod", "logs": root / "logs/obsgod"}
    variables = {"plugin": "DECKY_PLUGIN_DIR", "settings": "DECKY_PLUGIN_SETTINGS_DIR",
                 "data": "DECKY_PLUGIN_RUNTIME_DIR", "logs": "DECKY_PLUGIN_LOG_DIR"}
    for key, name in variables.items():
        value = values.get(name, "")
        if value and Path(value) != expected[key]:
            raise ValueError(name + " disagrees with the stable obsgod directory under DECKY_HOME")
    for path in expected.values():
        for parent in [path, *path.parents]:
            if parent in (Path(home), Path(home).resolve()) or not parent.resolve().is_relative_to(Path(home).resolve()):
                continue
            if parent.is_symlink():
                raise ValueError("Refusing a symlinked Decky directory")
    return expected
