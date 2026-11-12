#!/usr/bin/env python3
"""Historical updater-4 qualification against its second-WebSocket protocol.

Use decky-transport-smoke.py for Roadmap 1 candidates; this harness only
reproduces the previously shipped updater/source and must not qualify new code.

Upstream GPL sources are fetched outside this repository, never redistributed in
the product. Real loader lifecycle, ownership operations and Steam are fixtures.
"""
import argparse
import asyncio
from enum import Enum
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import types
import zipfile

from aiohttp import web
from test_bootstrap import desktop_command

PINNED_BLOBS = {
    "browser.py": "81ae4461c074cae4724681d1b9fd8a2f6a521349",
    "helpers.py": "bc3302982510e17649937df0d4afc43c265a717d",
    "wsrouter.py": "b0610b317b4375c61f1bfba74b85f6197a92afda",
}


def add_module(name):
    module = types.ModuleType(name)
    module.__path__ = []
    sys.modules[name] = module
    return module


def import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def upstream_modules(directory):
    for name, expected in PINNED_BLOBS.items():
        data = (directory / name).read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        assert actual == expected, "Upstream source differs from pinned Decky 3.3.1: " + name
    add_module("decky_loader")
    add_module("decky_loader.localplatform")
    platform = add_module("decky_loader.localplatform.localplatform")
    platform.chown = lambda *args, **kwargs: True
    platform.chmod = lambda *args, **kwargs: True
    platform.get_chown_plugin_path = lambda: True
    platform.ON_LINUX = True
    platform.ON_WINDOWS = False
    enums = add_module("decky_loader.enums")
    enums.UserType = Enum("UserType", ["HOST_USER", "EFFECTIVE_USER"])
    add_module("decky_loader.plugin")
    messages = add_module("decky_loader.plugin.messages")
    messages.PluginStopped = type("PluginStopped", (Exception,), {})
    loader = add_module("decky_loader.loader")
    loader.Loader = object
    loader.Plugins = dict
    settings = add_module("decky_loader.settings")
    settings.SettingsManager = object
    helpers = import_file("decky_loader.helpers", directory / "helpers.py")
    router = import_file("decky_loader.wsrouter", directory / "wsrouter.py")
    browser = import_file("decky_loader.browser", directory / "browser.py")
    return helpers, router, browser


class Settings:
    def __init__(self):
        self.values = {"pluginOrder": ["Alpha", "OBSGod", "Beta"], "frozenPlugins": ["Alpha"], "hiddenPlugins": ["Beta"], "disabled_plugins": []}

    def getSetting(self, key, default=None):
        return self.values.get(key, default)

    def setSetting(self, key, value):
        self.values[key] = value


class Plugin:
    def __init__(self, name, version, directory):
        self.name, self.version, self.plugin_directory = name, version, directory
        self.disabled, self.load_type = False, 1

    def get_display_name(self):
        return self.name + " " + self.version

    async def stop(self, **_):
        pass  # Actual Steam/Decky process lifecycle is unavailable in this fixture.


class Loader:
    watcher = None

    def __init__(self, ws, path):
        self.ws, self.path = ws, path
        self.plugins = {name: Plugin(name, "0.1.0-old", name.lower()) for name in ["Alpha", "OBSGod", "Beta"]}

    async def import_plugin(self, file, folder):
        root = Path(file).parent
        plugin = json.loads((root / "plugin.json").read_text())
        metadata = json.loads((root / "package.json").read_text())
        self.plugins[plugin["name"]] = Plugin(plugin["name"], metadata["version"], folder)

    async def get_plugins(self):
        return [{"name": plugin.name, "version": plugin.version, "load_type": plugin.load_type, "disabled": plugin.disabled} for plugin in self.plugins.values()]


async def execute(command, env, timeout=90, input_data=None, **kwargs):
    if input_data is not None:
        kwargs["stdin"] = asyncio.subprocess.PIPE
    process = await asyncio.create_subprocess_exec(*command, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, **kwargs)
    try:
        output, _ = await asyncio.wait_for(process.communicate(input_data), timeout)
    except BaseException:
        if process.returncode is None:
            process.kill()
            await process.wait()
        raise
    assert process.returncode == 0, output.decode(errors="replace")
    assert b"fixture-stream-key-never-real" not in output
    return output


async def run(args):
    helpers, router, browser = upstream_modules(args.upstream)
    with tempfile.TemporaryDirectory(prefix="obsgod-updater-smoke-") as temporary:
        base = Path(temporary)
        home = base / "home with spaces %20"
        home.mkdir()
        env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"), XDG_STATE_HOME=str(home / ".local/state"), XDG_CURRENT_DESKTOP="KDE", DESKTOP_SESSION="plasma")
        older = base / "older"
        older.mkdir()
        with tarfile.open(args.previous_archive) as archive:
            archive.extractall(older, filter="data")
        old_package = next(older.glob("OBSGod-*"))
        await execute([sys.executable, str(old_package / "install.py"), "--no-launch"], env)
        current = home / ".local/share/obsgod/current"
        configured = subprocess.run([str(current / "obsgod"), "deck", "configure"], input=json.dumps({"server":"rtmps://example.invalid/app", "stream_key":"fixture-stream-key-never-real"}), env=env, capture_output=True, text=True, check=True)
        assert "fixture-stream-key-never-real" not in configured.stdout + configured.stderr
        for path in [home / "Videos/OBSGod/keep.mkv", home / ".var/app/com.obsproject.Studio/config/obsgod/obs-studio/global.ini"]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"unchanged fixture data")
        protected = [home / ".config/obsgod/deck.json", home / ".config/obsgod/secrets.json", home / "Videos/OBSGod/keep.mkv", home / ".var/app/com.obsproject.Studio/config/obsgod/obs-studio/global.ini"]
        snapshots = {path:path.read_bytes() for path in protected}
        plugins = home / "homebrew/plugins"
        plugins.mkdir(parents=True)
        with zipfile.ZipFile(old_package / "obsgod-decky.zip") as archive:
            archive.extractall(plugins)
        for name in ["Alpha", "Beta"]:
            folder = plugins / name.lower()
            folder.mkdir()
            (folder / "plugin.json").write_text(json.dumps({"name":name}))
            (folder / "keep").write_bytes(b"unrelated plugin bytes")
        updater = base / "updater with spaces %20"
        updater.mkdir()
        with zipfile.ZipFile(args.updater_zip) as archive:
            archive.extractall(updater)
        package = updater / "OBSGod-Updater"
        commands = base / "fixture-bin"
        commands.mkdir()
        (commands / "flatpak").write_text("#!/bin/sh\ntest \"$1\" = info\n")
        dialog = base / "dialog-message"
        (commands / "kdialog").write_text("#!" + sys.executable + "\nimport os,sys\nfrom pathlib import Path\nPath(os.environ['OBSGOD_FIXTURE_DIALOG']).write_text(sys.argv[-1])\n")
        for path in commands.iterdir():
            path.chmod(0o700)
        env.update(PATH=str(commands) + os.pathsep + os.environ["PATH"], OBSGOD_FIXTURE_DIALOG=str(dialog))

        app = web.Application(middlewares=[helpers.csrf_middleware])
        ws = router.WSRouter(asyncio.get_running_loop(), app)
        loader = Loader(ws, plugins)
        settings = Settings()
        installer = browser.PluginBrowser(str(plugins), loader.plugins, loader, settings)

        async def auth(_):
            return web.Response(text=helpers.get_csrf_token())

        async def request_install(*values):
            return await installer.request_plugin_install(*values)

        async def confirm(request):
            return await installer.confirm_plugin_install(request)

        async def get_setting(key, default=None):
            return settings.getSetting(key, default)

        async def set_setting(key, value):
            return settings.setSetting(key, value)

        app.add_routes([web.get("/auth/token", auth)])
        ws.add_route("utilities/install_plugin", request_install)
        ws.add_route("utilities/confirm_plugin_install", confirm)
        ws.add_route("utilities/settings/get", get_setting)
        ws.add_route("utilities/settings/set", set_setting)
        ws.add_route("loader/get_plugins", loader.get_plugins)
        server = web.AppRunner(app, access_log=None)
        await server.setup()
        site = web.TCPSite(server, "127.0.0.1", 1337)
        await site.start()
        try:
            # The actual desktop entry finds its script through a file URI,
            # including spaces and literal percent sequences. No bypass of main.
            command = desktop_command(package / "Update OBSGod.desktop", as_uri=True)
            output = await execute(command, env, cwd=home)
            assert b"DONE:" in output
            assert "0.1.0-deck.4" in dialog.read_text()
            assert all(path.read_bytes() == data for path,data in snapshots.items())
            assert json.loads((plugins / "obsgod/package.json").read_text())["version"] == "0.1.0-deck.4"
            assert settings.getSetting("pluginOrder") == ["Alpha", "OBSGod", "Beta"]
            assert settings.getSetting("frozenPlugins") == ["Alpha"]
            assert settings.getSetting("hiddenPlugins") == ["Beta"]
            for name in ["alpha", "beta"]:
                assert (plugins / name / "keep").read_bytes() == b"unrelated plugin bytes"
            backup = list((home / ".local/share/obsgod/backups").glob("updater-*/secrets.json"))
            assert len(backup) == 1 and backup[0].stat().st_mode & 0o777 == 0o600
            # Rerun the same script: no manual removal, extra input or key reset.
            await execute(command, env, cwd=home)
            assert all(path.read_bytes() == data for path,data in snapshots.items())
            assert settings.getSetting("pluginOrder") == ["Alpha", "OBSGod", "Beta"]
            assert not list((home / ".local/share/obsgod").glob(".update-*"))
            assert (home / ".local/share/obsgod/releases/0.1.0-deck.1").is_dir()
            print("PASS: actual updater ZIP + desktop/file-URI launcher + compiled authenticated client + pinned Decky 3.3.1 CSRF/router/installer; original-preview app/plugin replacement, repeat run, private backup, settings/key/media/OBS preservation and other plugin/order preservation. Ownership, loader lifecycle, dialogs, Flatpak info and Steam are fixtures; real Deck untested.")
        finally:
            await server.cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("updater_zip", type=Path)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--previous-archive", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
