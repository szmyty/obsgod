"""Decky-owned metadata around one retained, shared managed-OBS store.

This compatibility transition never copies credentials or relocates managed
state/locks. Old CLI/Desktop clients continue to use the same XDG files. Loader
persistent runtime data is for plugin jobs, not XDG_RUNTIME_DIR/session sockets.
"""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import tempfile

MAP_ENV = "OBSGOD_DECKY_STORAGE_MAP"
SCHEMA = "obsgod.decky-storage-map/v1"
ERROR = "Decky storage context is unsafe or unavailable. Reload or repair the plugin."
MISMATCH = "Decky storage map does not match the current player paths. Restore the original context before retrying."
LIMIT = 65536


def _value(provided, name):
    value = provided(name) if callable(provided) else provided.get(name)
    return value or None


def _path(value):
    if (not isinstance(value, str) or not value or not Path(value).is_absolute()
            or any(ord(c) < 32 or ord(c) == 127 for c in value)
            or ".." in Path(value).parts):
        raise OSError(ERROR)
    return Path(value)


def _checked(path, directory=True, private=False, missing=False):
    """Reject links/foreign ownership without changing existing permissions."""
    path = _path(str(path))
    for component in (*reversed(path.parents), path):
        try:
            info = component.lstat()
        except FileNotFoundError:
            if missing:
                return path
            raise OSError(ERROR) from None
        if stat.S_ISLNK(info.st_mode):
            raise OSError(ERROR)
        if component != path and not stat.S_ISDIR(info.st_mode):
            raise OSError(ERROR)
        if info.st_uid not in (0, os.getuid()):
            raise OSError(ERROR)
        if stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) & 0o022 and not info.st_mode & stat.S_ISVTX:
            # A private leaf is insufficient: another user can rename it via
            # a non-sticky writable ancestor and split the controller inode.
            raise OSError(ERROR)
    info = path.lstat()
    if info.st_uid != os.getuid() or (directory and not stat.S_ISDIR(info.st_mode)):
        raise OSError(ERROR)
    if not directory and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > LIMIT):
        raise OSError(ERROR)
    if private and stat.S_IMODE(info.st_mode) & 0o077:
        raise OSError(ERROR)
    return path


def _private_directory(path):
    _checked(path, missing=True)
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    return _checked(path, private=True)


def _json(path):
    _checked(path, directory=False, private=True)
    descriptor = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 or info.st_mode & 0o077:
            raise OSError(ERROR)
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            descriptor = None
            data = stream.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise OSError(ERROR)
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError()
                result[key] = value
            return result
        return json.loads(data, object_pairs_hook=unique)
    except (ValueError, UnicodeError):
        raise OSError(ERROR) from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _write_new(path, value):
    data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    descriptor, temporary = tempfile.mkstemp(prefix=".storage-", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # link is atomic and refuses to replace any existing file or symlink.
        # The temporary hardlink is immediately removed before another reader.
        os.link(temporary, str(path), follow_symlinks=False)
    finally:
        os.unlink(temporary)


def _player_environment(provided, environ):
    child = dict(environ)
    # Only a newly validated loader context can activate this bridge.
    for name in (MAP_ENV, "OBSGOD_DECKY_RUNTIME_DIR", "OBSGOD_DECKY_LOG_DIR"):
        child.pop(name, None)
    value = _value(provided, "DECKY_USER_HOME")
    if value is not None:
        original_home = _path(value)
        try:
            home = original_home.resolve(strict=True)
        except (OSError, RuntimeError):
            raise OSError(ERROR) from None
        _checked(home)
        old_home = child.get("HOME")
        child["HOME"] = str(home)
        for name in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
            setting = child.get(name)
            if not setting:
                continue
            try:
                candidate = _path(setting)
            except OSError:
                child.pop(name, None)
                continue
            if (old_home and old_home != "/" and Path(old_home).is_absolute()
                    and Path(old_home).resolve() != home and candidate.is_relative_to(old_home)):
                child.pop(name, None)
            elif candidate.is_relative_to(original_home):
                child[name] = str(home / candidate.relative_to(original_home))
    user = _value(provided, "DECKY_USER")
    if isinstance(user, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,63}", user):
        child["USER"] = child["LOGNAME"] = user
    return child


def _derived(child):
    home = _checked(_path(child.get("HOME")))
    config_root = _path(child.get("XDG_CONFIG_HOME") or str(home / ".config"))
    state_root = _path(child.get("XDG_STATE_HOME") or str(home / ".local/state"))
    config = config_root / "obsgod/deck.json"
    secrets = config_root / "obsgod/secrets.json"
    state = state_root / "obsgod"
    _checked(config.parent, missing=True)
    _checked(config, directory=False, missing=True)
    _checked(secrets, directory=False, private=True, missing=True)
    _checked(state, directory=True, private=True, missing=True)
    return home, {"config": str(config), "secrets": str(secrets), "state": str(state)}


def _layout(plugin_root, provided, child):
    keys = ("DECKY_PLUGIN_SETTINGS_DIR", "DECKY_PLUGIN_RUNTIME_DIR", "DECKY_PLUGIN_LOG_DIR")
    supplied = [_value(provided, name) for name in keys]
    # Older loaders retain their prior child context without creating files.
    if not all(supplied):
        return {"mode": "legacy", "home": child.get("HOME"), "settings_dir": None,
                "runtime_dir": None, "log_dir": None, "jobs_dir": None, "map_path": None,
                "shared_state": None}, None
    home, shared = _derived(child)
    user = _value(provided, "DECKY_USER")
    if user is not None:
        try:
            if not isinstance(user, str) or pwd.getpwnam(user).pw_uid != os.getuid():
                raise OSError(ERROR)
        except KeyError:
            raise OSError(ERROR) from None
    if os.geteuid() != os.getuid() or os.geteuid() == 0:
        raise OSError(ERROR)
    # Paths supplied through /home's system alias are normalized using the
    # already verified player home; links within storage roots remain forbidden.
    raw_home = _path(_value(provided, "DECKY_USER_HOME") or str(home))
    roots = []
    for value in supplied:
        path = _path(value)
        if path.is_relative_to(raw_home):
            path = home / path.relative_to(raw_home)
        _checked(path, missing=True)
        roots.append(path)
    settings, runtime, logs = roots
    plugin = _path(str(plugin_root)).resolve(strict=True)
    if not plugin.is_dir() or any(root == plugin or root.is_relative_to(plugin) or plugin.is_relative_to(root) for root in roots):
        raise OSError(ERROR)
    if any(a == b or a.is_relative_to(b) or b.is_relative_to(a) for i, a in enumerate(roots) for b in roots[i + 1:]):
        raise OSError(ERROR)
    for root in roots:
        if root == Path(shared["state"]) or root == Path(shared["config"]).parent:
            raise OSError(ERROR)
    for path in roots:
        if not path.exists():
            _checked(path.parent)
            path.mkdir(mode=0o700)
        _checked(path)
    map_root = _private_directory(settings / "storage-v1")
    map_path = map_root / "map.json"
    expected = {"schema": SCHEMA, "version": 1, "uid": os.getuid(), "home": str(home),
                "shared": shared, "decky": {"settings": str(settings), "runtime": str(runtime), "logs": str(logs)},
                "compatibility": {"cli": "obsgod", "plugin": "OBSGod", "storage_namespace": "obsgod"}}
    return {"mode": "decky", "home": str(home), "settings_dir": str(settings), "runtime_dir": str(runtime),
            "log_dir": str(logs), "jobs_dir": str(runtime / "jobs"), "map_path": str(map_path),
            "shared_state": shared["state"]}, expected


def _prepare(layout, expected):
    if expected is None:
        return
    map_path = Path(layout["map_path"])
    lock = map_path.parent / "map.lock"
    _checked(lock, directory=False, private=True, missing=True)
    descriptor = os.open(str(lock), os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 or info.st_mode & 0o077:
            raise OSError(ERROR)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        existed = map_path.exists()
        if existed:
            if json.dumps(_json(map_path), sort_keys=True) != json.dumps(expected, sort_keys=True):
                raise OSError(MISMATCH)
        else:
            _write_new(map_path, expected)
        receipt_path = map_path.parent / "migration.json"
        digest = hashlib.sha256(map_path.read_bytes()).hexdigest()
        if receipt_path.exists():
            receipt = _json(receipt_path)
            if (not isinstance(receipt, dict) or receipt.get("schema") != "obsgod.decky-storage-receipt/v1" or receipt.get("map_sha256") != digest
                    or receipt.get("uid") != os.getuid() or receipt.get("transition") != "retained-shared-xdg"):
                raise OSError(MISMATCH)
        else:
            _write_new(receipt_path, {"schema": "obsgod.decky-storage-receipt/v1", "version": 1, "uid": os.getuid(),
                "transition": "retained-shared-xdg", "map_sha256": digest,
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "observation": "receipt-repair" if existed else "initial-adoption",
                "legacy_settings_present": Path(expected["shared"]["config"]).exists(),
                "legacy_credentials_present": Path(expected["shared"]["secrets"]).exists(),
                "credential_copy": False, "managed_state_move": False,
                "rollback": "remove only this validated storage map/receipt; shared credentials, state, locks and media remain"})
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def context(plugin_root, provided, environ=None):
    """Prepare private adapter metadata and return paths; never return secrets."""
    try:
        child = _player_environment(provided, os.environ if environ is None else environ)
        layout, expected = _layout(plugin_root, provided, child)
        _prepare(layout, expected)
        return layout
    except (OSError, ValueError, RuntimeError) as error:
        raise OSError(MISMATCH if str(error) == MISMATCH else ERROR) from None


def child_environment(plugin_root, provided, environ=None):
    """Return an isolated child environment, preserving the real session bus."""
    try:
        child = _player_environment(provided, os.environ if environ is None else environ)
        layout, expected = _layout(plugin_root, provided, child)
        _prepare(layout, expected)
        if expected is not None:
            child[MAP_ENV] = layout["map_path"]
            child["OBSGOD_DECKY_RUNTIME_DIR"] = layout["runtime_dir"]
            child["OBSGOD_DECKY_LOG_DIR"] = layout["log_dir"]
        return child
    except (OSError, ValueError, RuntimeError) as error:
        raise OSError(MISMATCH if str(error) == MISMATCH else ERROR) from None


# The integration may use either spelling; both produce a child-only mapping.
environment = child_environment


def _rollback(plugin_root, provided, environ=None):
    """Remove only matching private metadata; no data/controller state is moved."""
    child = _player_environment(provided, os.environ if environ is None else environ)
    layout, expected = _layout(plugin_root, provided, child)
    if expected is None:
        return {"removed": False, "shared_store_preserved": True}
    map_path = Path(layout["map_path"])
    receipt_path = map_path.parent / "migration.json"
    for path in (map_path, receipt_path):
        _checked(path, directory=False, private=True, missing=True)
    if not map_path.exists() and not receipt_path.exists():
        return {"removed": False, "shared_store_preserved": True}
    _prepare(layout, expected)
    descriptor = os.open(str(map_path.parent / "map.lock"), os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        if (_json(map_path) != expected or _json(receipt_path).get("map_sha256") != hashlib.sha256(map_path.read_bytes()).hexdigest()):
            raise OSError(MISMATCH)
        for path in (receipt_path, map_path):
            _checked(path, directory=False, private=True)
            path.unlink()
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
    return {"removed": True, "shared_store_preserved": True}


def rollback(plugin_root, provided, environ=None):
    try:
        return _rollback(plugin_root, provided, environ)
    except (OSError, ValueError, RuntimeError) as error:
        raise OSError(MISMATCH if str(error) == MISMATCH else ERROR) from None
