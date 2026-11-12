#!/usr/bin/env python3
"""Exercise the compiled installer with pinned Decky backend/frontend routers.

Steam's CDP evaluation and service ownership/lifecycle are fixtures. The unchanged
Decky 3.3.1 WSRouter, frontend WSRouter and PluginBrowser execute real requests.
This is protocol evidence, not Steam Deck qualification.
"""
import argparse
import asyncio
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
import zipfile

import aiohttp
from aiohttp import web

REPO = Path(__file__).resolve().parents[2]


def fixture_module():
    spec = importlib.util.spec_from_file_location("updater_smoke_fixture", REPO / "steamdeck/tests/updater-smoke.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def old_transport_reproduction(router, helpers):
    app = web.Application(middlewares=[helpers.csrf_middleware])
    ws = router.WSRouter(asyncio.get_running_loop(), app)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    async with aiohttp.ClientSession() as client:
        endpoint = f"http://127.0.0.1:{port}/ws?auth={helpers.get_csrf_token()}"
        first = await client.ws_connect(endpoint)
        first_receive = asyncio.create_task(first.receive())
        second = await client.ws_connect(endpoint)
        await asyncio.wait_for(first_receive, 3)
        # Observe the original connection's cleanup without assuming a fixed
        # scheduling order between the two WebSocket handlers.
        for _ in range(30):
            if ws.ws is None:
                break
            await asyncio.sleep(0.01)
        assert first.closed and not second.closed, "competing transport did not displace the original frontend"
        # Exact slot-clearing order is event-loop dependent; the guaranteed
        # defect is displacement of the real frontend and subsequent reconnect
        # contention, not a deterministic assertion that the slot is None.
        await second.close()
    await runner.cleanup()


def build_router(upstream, output):
    data = (upstream / "wsrouter.ts").read_bytes()
    digest = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    assert digest == "5d02fc0c752e84470ae1309b20b76d6bd861b556", "Frontend WSRouter differs from pinned Decky 3.3.1"
    # Bundle the original router with harmless fixture-only logging and sleep
    # adapters. The transport, response matching and event logic are unchanged.
    script = """
const esbuild=require(process.argv[1]);
esbuild.build({entryPoints:[process.argv[2]],outfile:process.argv[3],bundle:true,platform:'node',format:'esm',
 plugins:[{name:'fixture-platform',setup(build){
 build.onResolve({filter:/^(@decky\\/ui|\\.\\/logger)$/},args=>({path:args.path,namespace:'fixture'}));
 build.onLoad({filter:/.*/,namespace:'fixture'},args=>({contents:args.path==='@decky/ui'?
  'export const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));':
  'export default class Logger {debug(){} warn(){} error(){} log(){}}'}));
 }}]}).catch(()=>process.exit(1));
"""
    subprocess.run(["node", "-e", script, str(REPO / "steamdeck/decky/node_modules/esbuild"), str(upstream / "wsrouter.ts"), str(output)], check=True)


NODE_FRONTEND = r"""
import http from 'node:http';
const {WSRouter}=await import(process.argv[2]);
globalThis.window=globalThis;
globalThis.deckyAuthToken=await (await fetch('http://127.0.0.1:1337/auth/token')).text();
globalThis.DeckyBackend=new WSRouter();
await DeckyBackend.connect();
const originalSocket=DeckyBackend.ws;
const prompts=[];
const event='loader/add_plugin_install_prompt';
const listener=(name)=>prompts.push(name);
DeckyBackend.addEventListener(event,listener);
const server=http.createServer(async(req,res)=>{
 let input='';for await(const part of req)input+=part;
 try{
  const value=await eval(JSON.parse(input).code);
  if(DeckyBackend.ws!==originalSocket||originalSocket.readyState!==1)throw Error('frontend socket changed');
  if(DeckyBackend.eventListeners.get(event)?.size!==1||!DeckyBackend.eventListeners.get(event)?.has(listener))throw Error('listener changed');
  res.setHeader('Content-Type','application/json');res.end(JSON.stringify({value,prompts}));
 }catch(_){res.statusCode=500;res.end('{}')}
});
server.listen(0,'127.0.0.1',()=>process.stdout.write(JSON.stringify({port:server.address().port})+'\n'));
"""


async def runtime_installer_upgrade(fixture, args, work, plugins, loader, settings):
    """Run the packaged default unified installer; preserve actual user files."""
    home = work / "home with spaces %20"
    home.mkdir()
    env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"),
               XDG_STATE_HOME=str(home / ".local/state"), XDG_CURRENT_DESKTOP="KDE", DESKTOP_SESSION="plasma")
    previous = work / "previous runtime"
    previous.mkdir()
    with tarfile.open(args.previous_archive) as archive:
        archive.extractall(previous, filter="data")
    previous_package = next(previous.glob("OBSGod-*"))
    await fixture.execute([sys.executable, str(previous_package / "install.py"), "--no-launch"], env)
    current = home / ".local/share/obsgod/current"
    previous_release = current.resolve()
    configured = subprocess.run([str(current / "obsgod"), "deck", "configure"],
        input=json.dumps({"server":"rtmps://example.invalid/app", "stream_key":"fixture-stream-key-never-real"}),
        env=env, capture_output=True, text=True, check=True)
    assert "fixture-stream-key-never-real" not in configured.stdout + configured.stderr
    protected = [
        home / ".config/obsgod/deck.json", home / ".config/obsgod/secrets.json",
        home / "Videos/OBSGod/keep.mkv", home / ".local/state/obsgod/diagnostics/keep.json",
        home / ".var/app/com.obsproject.Studio/config/obsgod/obs-studio/global.ini",
        home / ".var/app/com.obsproject.Studio/config/obs-studio/global.ini",
    ]
    for path in protected[2:]:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(b"preserved fixture user data")
    snapshots = {path:path.read_bytes() for path in protected}
    history = home / ".local/state/obsgod/diagnostics/events.json"
    saved_event = {"time":"2026-11-11T00:00:00Z","code":"operation.succeeded"}
    history.write_text(json.dumps([saved_event]))
    history.chmod(0o600)
    old_metadata = json.loads(zipfile.ZipFile(previous_package / "obsgod-decky.zip").read("obsgod/package.json"))
    if (plugins / "obsgod").exists():
        shutil.rmtree(plugins / "obsgod")  # Disposable fixture only.
    with zipfile.ZipFile(previous_package / "obsgod-decky.zip") as archive:
        archive.extractall(plugins)
    loader.plugins["OBSGod"] = fixture.Plugin("OBSGod", old_metadata["version"], "obsgod")

    candidate = work / "candidate runtime with spaces %20"
    candidate.mkdir()
    with tarfile.open(args.runtime_archive) as archive:
        archive.extractall(candidate,filter="data")
    package = next(candidate.glob("OBSGod-*"))
    manifest = json.loads((package / "manifest.json").read_text())
    commands = work / "fixture-bin"
    commands.mkdir()
    # Reject unsupported CLI options, including the old invented --show-version.
    (commands / "flatpak").write_text("#!" + sys.executable + "\n" + """
import sys
args = sys.argv[1:]
obs = 'com.obsproject.Studio'
ref = 'app/' + obs + '/x86_64/stable'
if args in [['info', '--user', obs], ['info', '--user', obs + '.Plugin.Gstreamer']]:
    pass
elif args == ['info', '--user', '--show-ref', obs]:
    print(ref)
elif args == ['list', '--user', '--app', '--columns=ref,version']:
    print(ref.removeprefix('app/') + '\\t33.0.1')
else:
    print('Unsupported Flatpak fixture command', file=sys.stderr)
    raise SystemExit(2)
""")
    (commands / "flatpak").chmod(0o700)
    env["PATH"] = str(commands) + os.pathsep + os.environ["PATH"]
    for _ in range(2):
        output = await fixture.execute([sys.executable,str(package / "install.py"),"--no-launch"],env)
        assert b"in the app and Decky" in output, output
        assert all(path.read_bytes() == value for path,value in snapshots.items())
        assert saved_event in json.loads(history.read_text()), "diagnostic history was reset"
        assert json.loads((current / "manifest.json").read_text())["version"] == manifest["version"]
        assert json.loads((plugins / "obsgod/package.json").read_text())["version"] == manifest["version"]
        assert settings.getSetting("pluginOrder") == ["Alpha","OBSGod","Beta"]
        assert settings.getSetting("frozenPlugins") == ["Alpha"]
        assert settings.getSetting("hiddenPlugins") == ["Beta"]
        assert all((plugins/name/"keep").read_text() == "unrelated plugin data" for name in ["alpha","beta"])
        assert (home / ".local/share/applications/obsgod-update.desktop").is_file()
        assert (current / "update.py").is_file() and (current / "releases.py").is_file()
        assert not (current.parent / "installation-recovery.json").exists()
    assert previous_release.is_dir(), "previous runtime was removed"
    assert current.resolve() != previous_release, "candidate app was not activated"
    assert not list(current.parent.glob(".install-*"))
    print("PASS: actual runtime archive default unified install.py --no-launch upgraded " + old_metadata["version"] +
          " to " + manifest["version"] + " and repeated same-version installation; authenticated active-frontend plugin replacement, app/plugin pair, bundled updater/menu entry, private settings/key, recordings, ordinary/managed OBS files, diagnostic data, prior release and unrelated plugins/order preserved. Flatpak installation/version, Steam/CDP and loader ownership/lifecycle are fixtures.")
    if args.updater_zip:
        await desktop_updater_upgrade(fixture, args, work, env, previous_package, package,
                                      current, plugins, loader, settings, snapshots,
                                      history, saved_event, manifest)


async def desktop_updater_upgrade(fixture, args, work, env, previous_package, package,
                                  current, plugins, loader, settings, snapshots,
                                  history, saved_event, manifest):
    """Run the unmodified extracted Desktop updater with network responses staged.

    sitecustomize exists only in this disposable fixture. It substitutes HTTPS
    responses at urllib's boundary; the real discovery/origin/tag/checksum,
    archive download/verification/extraction and unified installer all execute.
    No product environment variable or arbitrary runtime URL bypass is added.
    """
    extracted = work / "updater package with spaces %20"
    extracted.mkdir()
    with zipfile.ZipFile(args.updater_zip) as archive:
        archive.extractall(extracted)
    updater = extracted / "OBSGod-Updater"
    assert (updater / "update.py").is_file()
    network = work / "updater-network-fixture"
    network.mkdir()
    version = manifest["version"]
    archive_name = "obsgod-deck_" + version + "_linux_amd64.tar.gz"
    base_url = "https://github.com/szmyty/obsgod/releases/download/v" + version + "/"
    release = {"tag_name": "v" + version, "target_commitish": manifest["revision"],
               "draft": False, "prerelease": "-" in version,
               "assets": [{"name": name, "browser_download_url": base_url + name}
                          for name in [archive_name, "manifest.json", "SHA256SUMS"]]}
    # An updater-only release with a higher version must never become the
    # streaming runtime. This also exercises the real release-list filtering.
    release_list = network / "releases.json"
    release_list.write_text(json.dumps([
        {"tag_name": "v99.0.0-updater.1", "draft": False, "prerelease": True, "assets": []},
        release]))
    commit = network / "commit.json"
    commit.write_text(json.dumps({"sha": manifest["revision"]}))
    checksums = network / "SHA256SUMS"
    checksums.write_text(hashlib.sha256(args.runtime_archive.read_bytes()).hexdigest() + "  " + archive_name + "\n" +
                         hashlib.sha256((package / "manifest.json").read_bytes()).hexdigest() + "  manifest.json\n")
    responses = {
        "https://api.github.com/repos/szmyty/obsgod/releases?per_page=100": str(release_list),
        "https://api.github.com/repos/szmyty/obsgod/commits/v" + version: str(commit),
        base_url + "manifest.json": str(package / "manifest.json"),
        base_url + "SHA256SUMS": str(checksums),
        base_url + archive_name: str(args.runtime_archive.resolve()),
    }
    response_file = network / "responses.json"
    response_file.write_text(json.dumps(responses))
    (network / "sitecustomize.py").write_text(
        "import json,os,urllib.request\n"
        "from pathlib import Path\n"
        "_responses=json.loads(Path(os.environ['OBSGOD_UPDATE_TEST_RESPONSES']).read_text())\n"
        "def _fixture_open(request,*args,**kwargs):\n"
        "    url=request.full_url if isinstance(request,urllib.request.Request) else request\n"
        "    if url not in _responses: raise OSError('unexpected fixture network request')\n"
        "    return open(_responses[url],'rb')\n"
        "urllib.request.urlopen=_fixture_open\n")
    test_env = dict(env, OBSGOD_UPDATE_TEST_RESPONSES=str(response_file),
                    PYTHONPATH=str(network) + os.pathsep + env.get("PYTHONPATH", ""))
    # Desktop result dialogs are substituted, avoiding a hidden modal in CI.
    dialog = network / "last-dialog"
    dialogs = network / "bin"
    dialogs.mkdir()
    (dialogs / "kdialog").write_text("#!" + sys.executable + "\nimport sys\nfrom pathlib import Path\nPath(" + repr(str(dialog)) + ").write_text(sys.argv[-1])\n")
    (dialogs / "kdialog").chmod(0o700)
    test_env["PATH"] = str(dialogs) + os.pathsep + test_env["PATH"]

    # Start from the actual legacy app and plugin again; preserve its real key
    # and user data while exercising all current updater stages.
    await fixture.execute([sys.executable, str(previous_package / "install.py"), "--no-launch"], env)
    with zipfile.ZipFile(previous_package / "obsgod-decky.zip") as archive:
        shutil.rmtree(plugins / "obsgod")  # Disposable fixture only.
        archive.extractall(plugins)
    old_metadata = json.loads((plugins / "obsgod/package.json").read_text())
    loader.plugins["OBSGod"] = fixture.Plugin("OBSGod", old_metadata["version"], "obsgod")
    desktop_command = fixture.desktop_command(updater / "Update OBSGod.desktop", as_uri=True)
    output = await fixture.execute(desktop_command, test_env, cwd=current.parent)
    assert b"DONE:" in output and b"4/4 Verified" in output, output
    assert version in dialog.read_text()
    assert json.loads((current / "manifest.json").read_text())["revision"] == manifest["revision"]
    assert json.loads((plugins / "obsgod/package.json").read_text())["version"] == version
    assert all(path.read_bytes() == data for path, data in snapshots.items())
    assert saved_event in json.loads(history.read_text())
    assert json.loads((current.parent / "update-status.json").read_text())["state"] == "complete"
    assert settings.getSetting("pluginOrder") == ["Alpha", "OBSGod", "Beta"]
    assert not list(current.parent.glob(".update-*"))

    # A repeated Desktop invocation is an honest no-update result. Explicit
    # same-version repair executes the complete verified install path again.
    output = await fixture.execute(desktop_command, test_env, cwd=current.parent)
    assert b"Nothing was replaced" in output and b"3/4 Installing" not in output, output
    output = await fixture.execute([sys.executable, str(updater / "update.py"), "--repair"], test_env)
    assert b"4/4 Verified" in output, output

    # A corrupted archive fails its real expected checksum before replacement;
    # retain exact activated app/plugin/data and a concrete retry record.
    corrupted = network / "corrupted-archive"
    corrupted.write_bytes(b"fixture corrupted transfer")
    responses[base_url + archive_name] = str(corrupted)
    response_file.write_text(json.dumps(responses))
    activated = current.resolve()
    plugin_digest = hashlib.sha256((plugins / "obsgod/package.json").read_bytes()).hexdigest()
    process = await asyncio.create_subprocess_exec(sys.executable, str(updater / "update.py"), "--repair",
        env=test_env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    output, _ = await asyncio.wait_for(process.communicate(), 30)
    assert process.returncode == 1 and b"checksum does not match" in output, output
    assert current.resolve() == activated
    assert hashlib.sha256((plugins / "obsgod/package.json").read_bytes()).hexdigest() == plugin_digest
    assert all(path.read_bytes() == data for path, data in snapshots.items())
    assert b"fixture-stream-key-never-real" not in output
    assert json.loads((current.parent / "update-status.json").read_text())["state"] == "interrupted-or-failed"
    assert not list(current.parent.glob(".update-*"))
    backups = list((current.parent / "backups").glob("updater-*/secrets.json"))
    assert len(backups) == 2 and all(path.stat().st_mode & 0o777 == 0o600 for path in backups)
    print("PASS: actual extracted updater ZIP and Desktop/file-URI entry perform official-shape release discovery (skipping updater-only), exact tag/manifest/archive verification, legacy-to-candidate unified app/plugin upgrade, repeat no-update, explicit same-version repair, and checksum-failure preservation/recovery. HTTPS responses, Flatpak installation/version, dialogs, Steam/CDP and service ownership/lifecycle are fixtures; the product source and all verification/installer paths are unmodified.")


async def run(args):
    fixture = fixture_module()
    helpers, router, browser = fixture.upstream_modules(args.upstream)
    await old_transport_reproduction(router, helpers)
    with tempfile.TemporaryDirectory(prefix="obsgod-decky-transport-") as temporary:
        work = Path(temporary)
        plugins = work / "plugins"
        plugins.mkdir()
        for name in ["Alpha", "Beta"]:
            folder = plugins / name.lower()
            folder.mkdir()
            (folder / "plugin.json").write_text(json.dumps({"name":name}))
            (folder / "keep").write_text("unrelated plugin data")
        metadata = json.loads(zipfile.ZipFile(args.plugin_zip).read("obsgod/package.json"))
        source = work / "plugin.zip"
        shutil.copyfile(args.plugin_zip, source)
        source.chmod(0o600)
        payload = {"zip_path":str(source),"version":metadata["version"],"sha256":hashlib.sha256(source.read_bytes()).hexdigest()}
        bundle = work / "wsrouter.mjs"
        build_router(args.upstream, bundle)
        frontend_script = work / "frontend.mjs"
        frontend_script.write_text(NODE_FRONTEND)
        app = web.Application(middlewares=[helpers.csrf_middleware])
        ws = router.WSRouter(asyncio.get_running_loop(), app)
        loader = fixture.Loader(ws, plugins)
        # The old OBSGod plugin may be absent on a fresh install.
        loader.plugins.pop("OBSGod")
        settings = fixture.Settings()
        installer = browser.PluginBrowser(str(plugins), loader.plugins, loader, settings)
        connection_count = 0

        @web.middleware
        async def count_connections(request, handler):
            nonlocal connection_count
            if request.path == "/ws":
                connection_count += 1
            return await handler(request)

        app.middlewares.append(count_connections)

        async def auth(_):
            return web.Response(text=helpers.get_csrf_token())

        async def version():
            return {"current":"v3.3.1"}  # Installed loader/version lookup is a fixture.

        async def request_install(*values):
            await ws.emit("loader/add_plugin_install_prompt", "Other", "9.9.9", "unrelated", "0"*64, 4)
            return await installer.request_plugin_install(*values)

        async def get_setting(key, default=None):
            return settings.getSetting(key, default)

        async def set_setting(key, value):
            return settings.setSetting(key, value)

        frontend_port = None
        prompt_count = 0

        async def evaluate(request):
            nonlocal prompt_count
            data = await request.json()
            if data.get("tab") != "SP" or data.get("run_async") is not True:
                return web.json_response({"success":False,"result":None})
            # CDP is substituted with a private Node evaluator hosting the real
            # frontend router. Authentication/HTTP contract stays identical.
            async with aiohttp.ClientSession() as session:
                async with session.post(f"http://127.0.0.1:{frontend_port}",json={"code":data["code"]}) as response:
                    result = await response.json()
                    assert response.status == 200
            prompt_count = len(result["prompts"])
            return web.json_response({"success":True,"result":{"success":True,"result":result["value"]}})

        app.add_routes([web.get("/auth/token",auth),web.post("/methods/execute_in_tab",evaluate)])
        ws.add_route("updater/get_version_info",version)
        ws.add_route("utilities/install_plugin",request_install)
        ws.add_route("utilities/confirm_plugin_install",installer.confirm_plugin_install)
        ws.add_route("utilities/settings/get",get_setting)
        ws.add_route("utilities/settings/set",set_setting)
        ws.add_route("loader/get_plugins",loader.get_plugins)
        runner = web.AppRunner(app,access_log=None)
        await runner.setup()
        await web.TCPSite(runner,"127.0.0.1",1337).start()
        frontend = None
        try:
            frontend = await asyncio.create_subprocess_exec("node",str(frontend_script),str(bundle),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
            line = await asyncio.wait_for(frontend.stdout.readline(),10)
            assert line, await frontend.stderr.read()
            frontend_port = json.loads(line)["port"]
            for value in [{"operation":"probe"},payload,payload]:
                process = await asyncio.create_subprocess_exec(str(args.helper.resolve()),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
                output, errors = await asyncio.wait_for(process.communicate(json.dumps(value).encode()),90)
                assert process.returncode == 0,(output,errors)
                result = json.loads(output)
                assert result["ok"] and result["decky_version"] == "v3.3.1" and result["frontend_connected"]
                if value.get("operation") != "probe":
                    assert result["version"] == metadata["version"]
                assert connection_count == 1, "installer opened a competing frontend connection"
            assert prompt_count == 2, "unrelated prompt behavior changed"
            assert json.loads((plugins / "obsgod/package.json").read_text())["version"] == metadata["version"]
            assert settings.getSetting("pluginOrder") == ["Alpha","OBSGod","Beta"]
            assert settings.getSetting("frozenPlugins") == ["Alpha"]
            assert settings.getSetting("hiddenPlugins") == ["Beta"]
            assert all((plugins/name/"keep").read_text()=="unrelated plugin data" for name in ["alpha","beta"])
            assert not installer.install_requests, "unrelated request was confirmed or own request leaked"
            print("PASS: reproduced old competing-WS frontend displacement; compiled helper probe/install/reinstall through authenticated HTTP + unchanged Decky 3.3.1 frontend/backend routers and PluginBrowser, with one active frontend socket, own-only confirmation, unrelated prompts/plugins/order preserved. Steam/CDP, loader lifecycle/ownership and installed version lookup are fixtures; actual Steam Deck remains untested.")
            if args.runtime_archive:
                await runtime_installer_upgrade(fixture,args,work,plugins,loader,settings)
                assert connection_count == 1, "unified installer opened a competing frontend connection"
                assert prompt_count == (6 if args.updater_zip else 4), "unified installation changed unrelated prompt behavior"
                assert not installer.install_requests
        finally:
            if frontend is not None and frontend.returncode is None:
                frontend.terminate()
                await frontend.wait()
            await runner.cleanup()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("helper",type=Path)
    parser.add_argument("plugin_zip",type=Path)
    parser.add_argument("--upstream",type=Path,required=True)
    parser.add_argument("--runtime-archive",type=Path,help="Also execute the packaged default unified installer twice")
    parser.add_argument("--previous-archive",type=Path,help="Legacy runtime archive to upgrade in the unified-installer test")
    parser.add_argument("--updater-zip",type=Path,help="Also execute the extracted maintained Desktop updater with fixture release responses")
    args=parser.parse_args()
    if bool(args.runtime_archive) != bool(args.previous_archive):
        parser.error("--runtime-archive and --previous-archive must be provided together")
    if args.updater_zip and not args.runtime_archive:
        parser.error("--updater-zip requires --runtime-archive and --previous-archive")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
