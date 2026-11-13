"""Read and verify OBSGod runtime releases. Checking never changes an install.

Only this repository's GitHub releases and immutable same-repository artifact
commits are accepted. This is transport/checksum verification, not code signing.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = "szmyty/obsgod"
RELEASES_URL = "https://api.github.com/repos/" + REPOSITORY + "/releases?per_page=100"
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_METADATA = 2 * 1024 * 1024
UNIFIED_FILES = {"install.py", "decky.py", "decky-install", "update.py", "releases.py"}
_HEX = re.compile(r"[0-9a-f]{64}")
_SHA = re.compile(r"[0-9a-f]{40}")
_VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?")


class ReleaseError(RuntimeError):
    def __init__(self, message, state="error"):
        super().__init__(message)
        self.state = state


def version_key(value):
    """SemVer precedence, including numeric preview identifiers (9 < 10)."""
    if not isinstance(value, str) or len(value) > 80:
        raise ReleaseError("The installed or published version is invalid.")
    match = _VERSION.fullmatch(value)
    if not match:
        raise ReleaseError("The installed or published version is invalid.")
    major, minor, patch, preview = match.groups()
    parts = []
    if preview:
        for item in preview.split("."):
            if item.isdigit():
                if len(item) > 1 and item.startswith("0"):
                    raise ReleaseError("The published preview version is invalid.")
                parts.append((0, int(item)))
            else:
                parts.append((1, item))
    return (int(major), int(minor), int(patch), 1 if preview is None else 0, tuple(parts))


def _safe_url(url):
    if not isinstance(url, str) or any(c in url for c in "\r\n\x00"):
        return False
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment or port:
        return False
    if parsed.netloc == "api.github.com":
        return url == RELEASES_URL or bool(re.fullmatch(r"/repos/szmyty/obsgod/commits/v?[0-9A-Za-z.-]+", parsed.path) and not parsed.query)
    if parsed.query:
        return False
    if parsed.netloc == "raw.githubusercontent.com":
        return bool(re.fullmatch(r"/szmyty/obsgod/[0-9a-f]{40}/[A-Za-z0-9._-]+", parsed.path))
    if parsed.netloc == "github.com":
        return bool(re.fullmatch(r"/szmyty/obsgod/releases/download/v?[0-9A-Za-z.-]+/[A-Za-z0-9._-]+", parsed.path))
    return False


def _read_url(url, limit=MAX_METADATA):
    if not _safe_url(url):
        raise ReleaseError("Release metadata contains an unsupported download address.")
    request = urllib.request.Request(url, headers={"User-Agent": "OBSGod-updater", "Accept": "application/vnd.github+json" if "api.github.com/" in url else "application/octet-stream"})
    try:
        with _open_url(request, timeout=12) as response:
            data = response.read(limit + 1)
        if len(data) > limit:
            raise ReleaseError("Release metadata exceeded its size limit.")
        return data
    except urllib.error.HTTPError as error:
        if error.code in {403, 429}:
            raise ReleaseError("GitHub refused the update check or its rate limit was reached. Try again later.") from None
        raise ReleaseError("GitHub could not provide the release metadata. Try again later.") from None
    except ValueError:
        raise ReleaseError("GitHub returned an unsupported download address. Your installation is unchanged.", "unsupported") from None
    except (OSError, urllib.error.URLError):
        raise ReleaseError("Could not reach GitHub. Your installed version is unchanged; check your connection and retry.", "offline") from None


class _ProjectRedirects(urllib.request.HTTPRedirectHandler):
    """Reject moved-repository metadata before following an unapproved owner.

    GitHub release downloads use a signed CDN redirect. That single official
    asset hop is distinct from trusting another repository or arbitrary host.
    """
    def redirect_request(self, request, response, code, message, headers, url):
        try:
            source = urllib.parse.urlsplit(request.full_url)
            target = urllib.parse.urlsplit(url)
            allowed = (source.netloc == "github.com" and _safe_url(request.full_url) and
                       target.scheme == "https" and target.netloc == "release-assets.githubusercontent.com" and
                       target.username is None and target.password is None and target.port is None and
                       not target.fragment and not any(c in url for c in "\r\n\x00") and
                       bool(re.fullmatch(r"/github-production-release-asset/[0-9]+/[A-Za-z0-9-]+", target.path)))
        except ValueError:
            allowed = False
        if not allowed:
            raise ReleaseError("GitHub redirected outside the approved project update path. Your installation is unchanged; use a reviewed migration installer.", "unsupported")
        return super().redirect_request(request, response, code, message, headers, url)


def _open_url(request, timeout):
    return urllib.request.build_opener(_ProjectRedirects()).open(request, timeout=timeout)


def _json(url):
    try:
        return json.loads(_read_url(url))
    except (ValueError, UnicodeError):
        raise ReleaseError("GitHub returned unreadable release metadata.") from None


def _checksums(data):
    try:
        text = data.decode("ascii")
    except UnicodeError:
        raise ReleaseError("The release checksum list is invalid.") from None
    result = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64}) [ *]([A-Za-z0-9][A-Za-z0-9._-]{0,180})", line)
        if not match or match[2] in result:
            raise ReleaseError("The release checksum list contains an invalid or duplicate entry.")
        result[match[2]] = match[1]
    return result


def validate_manifest(manifest, version, revision):
    if not isinstance(manifest, dict) or manifest.get("version") != version or manifest.get("revision") != revision or manifest.get("platform") != "linux/amd64" or manifest.get("dirty") is not False:
        raise ReleaseError("The release manifest does not match its version, source revision or supported platform.")
    files = manifest.get("files")
    required = {"obsgod", "obsgod-decky.zip", "setup.py", "bridge.py"}
    if not isinstance(files, dict) or not required.issubset(files) or len(files) > 64:
        raise ReleaseError("The release manifest is incomplete.")
    for name, digest in files.items():
        if not isinstance(name, str) or name in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,180}", name) or not isinstance(digest, str) or not _HEX.fullmatch(digest):
            raise ReleaseError("The release manifest contains an unsafe file or checksum.")
    updater = manifest.get("updater_version")
    if updater is not None:
        version_key(updater)
    return manifest


def _locations(release, version):
    archive = "obsgod-deck_" + version + "_linux_amd64.tar.gz"
    names = {archive, "manifest.json", "SHA256SUMS"}
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        raise ReleaseError("The release asset list is invalid.")
    found = {}
    for asset in assets:
        if isinstance(asset, dict) and asset.get("name") in names:
            name = asset["name"]
            expected = "https://github.com/" + REPOSITORY + "/releases/download/" + release["tag_name"] + "/" + name
            if name in found or asset.get("browser_download_url") != expected:
                raise ReleaseError("A release asset has an unexpected address or duplicate name.")
            found[name] = expected
    if names.issubset(found):
        return archive, found
    # Historical previews were published with immutable artifact links because
    # release-asset upload was unavailable. Infer only this exact archive's
    # same-repository commit, never a mutable branch or a general Markdown URL.
    body = release.get("body") or ""
    if not isinstance(body, str):
        raise ReleaseError("The release description is invalid.")
    commits = set(re.findall(r"https://raw\.githubusercontent\.com/szmyty/obsgod/([0-9a-f]{40})/" + re.escape(archive) + r"(?=[\s)\]>]|$)", body))
    commits.update(re.findall(r"https://github\.com/szmyty/obsgod/raw/([0-9a-f]{40})/" + re.escape(archive) + r"(?=[\s)\]>]|$)", body))
    if len(commits) != 1:
        raise ReleaseError("The latest runtime release has no complete supported download metadata. Open its release page; your installation is unchanged.", "unsupported")
    base = "https://raw.githubusercontent.com/" + REPOSITORY + "/" + commits.pop() + "/"
    return archive, {name: base + name for name in names}


def _latest(channel):
    if channel not in {"stable", "preview"}:
        raise ReleaseError("Choose the stable or preview update channel.")
    releases = _json(RELEASES_URL)
    if not isinstance(releases, list) or len(releases) > 100:
        raise ReleaseError("GitHub returned an invalid release list.")
    candidates = []
    for release in releases:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        tag = release.get("tag_name", "")
        if not isinstance(tag, str) or "updater" in tag.lower():
            continue
        version = tag.removeprefix("v")
        try:
            key = version_key(version)
        except ReleaseError:
            continue
        preview = key[3] == 0
        if release.get("prerelease") is not preview or (channel == "stable" and preview):
            continue
        candidates.append((key, version, release))
    if not candidates:
        return None
    _, version, release = max(candidates, key=lambda item: item[0])
    archive, locations = _locations(release, version)
    # target_commitish is creation metadata and can name a mutable branch or
    # differ from a pre-existing/moved tag. Resolve the actual release tag.
    commit = _json("https://api.github.com/repos/" + REPOSITORY + "/commits/" + release["tag_name"])
    revision = commit.get("sha") if isinstance(commit, dict) else None
    if not isinstance(revision, str) or not _SHA.fullmatch(revision):
        raise ReleaseError("The release source revision could not be verified.")
    sums = _checksums(_read_url(locations["SHA256SUMS"]))
    if archive not in sums or "manifest.json" not in sums:
        raise ReleaseError("The release checksum list is missing the archive or manifest.")
    data = _read_url(locations["manifest.json"])
    if hashlib.sha256(data).hexdigest() != sums["manifest.json"]:
        raise ReleaseError("The release manifest checksum does not match.")
    try:
        manifest = validate_manifest(json.loads(data), version, revision)
    except (ValueError, UnicodeError):
        raise ReleaseError("The release manifest is unreadable.") from None
    return {"version": version, "revision": revision, "manifest": manifest, "manifest_sha256": sums["manifest.json"], "archive": archive, "archive_url": locations[archive], "archive_sha256": sums[archive], "release_url": "https://github.com/" + REPOSITORY + "/releases/tag/" + release["tag_name"]}


def inspect_updates(installed_version, channel="preview"):
    """Return public check result plus a private, verified download descriptor."""
    result = {"ok": False, "state": "error", "available": False, "current_version": installed_version, "latest_version": None, "revision": None, "channel": channel}
    try:
        current = version_key(installed_version)
        candidate = _latest(channel)
        if candidate is None:
            result.update(ok=True, state="unavailable", message="No runtime release is published for this channel. The installed version is unchanged.")
            return result, None
        available = version_key(candidate["version"]) > current
        unified = UNIFIED_FILES.issubset(candidate["manifest"]["files"])
        message = "No newer OBSGod runtime is available on this channel."
        if available:
            message = "OBSGod " + candidate["version"] + " is available. Stop output and use Update OBSGod in Desktop Mode to install it." if unified else "Historical OBSGod " + candidate["version"] + " is available. Open its official release page for installation instructions; it predates the unified updater."
        result.update(ok=True, state="update-available" if available else "up-to-date", available=available, latest_version=candidate["version"], revision=candidate["revision"], release_url=candidate["release_url"], latest_updater_version=candidate["manifest"].get("updater_version", "not-bundled"), automatic_update_supported=unified, message=message)
        return result, candidate
    except ReleaseError as error:
        result.update(state=error.state, message=str(error))
        return result, None


def check_updates(installed_version, channel="preview"):
    """Safe for the Decky backend: no writes, replacement, prompts or keys."""
    return inspect_updates(installed_version, channel)[0]


def current_versions(plugin_version="unknown", *, environ=None):
    """Read version identifiers only; never settings or stream credentials.

    The backend supplies the loaded plugin version. An unknown/unsafe app path
    remains unknown instead of claiming a matched pair from the plugin alone.
    """
    values = {"app": "unknown", "plugin": plugin_version, "updater": "not-bundled", "revision": None, "mismatch": False}
    try:
        version_key(plugin_version)
    except ReleaseError:
        values["plugin"] = "unknown"
    try:
        environment = os.environ if environ is None else environ
        raw_home = environment.get("HOME", str(Path.home()))
        if not isinstance(raw_home, str) or not Path(raw_home).is_absolute() or any(ord(c) < 32 for c in raw_home):
            return values
        home = Path(raw_home).resolve()
        # Load the bundled helper by its exact sibling path. Other Decky
        # plugins may have a different module called `paths` on sys.path.
        spec = importlib.util.spec_from_file_location("_obsgod_release_paths", Path(__file__).with_name("paths.py"))
        paths = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(paths)
        base, _ = paths.app_directories(home, environment)
        current = base / "current"
        if not current.is_symlink() or current.resolve().parent != (base / "releases").resolve() or not current.resolve().is_relative_to(home):
            return values
        saved = current / "manifest.json"
        if saved.is_symlink() or not saved.is_file() or saved.stat().st_size > 64 * 1024:
            return values
        manifest = json.loads(saved.read_text())
        version_key(manifest.get("version"))
        values["app"] = manifest["version"]
        updater = manifest.get("updater_version")
        if updater is not None:
            version_key(updater)
            values["updater"] = updater
        if isinstance(manifest.get("revision"), str) and _SHA.fullmatch(manifest["revision"]):
            values["revision"] = manifest["revision"]
        values["mismatch"] = values["plugin"] != "unknown" and values["app"] != values["plugin"]
    except (OSError, ValueError, TypeError, AttributeError, RuntimeError, ReleaseError):
        pass
    return values


def download_archive(candidate, destination):
    if not _safe_url(candidate["archive_url"]):
        raise ReleaseError("The release archive address is unsupported.")
    deadline = time.monotonic() + 180
    digest = hashlib.sha256()
    total = 0
    request = urllib.request.Request(candidate["archive_url"], headers={"User-Agent": "OBSGod-updater"})
    try:
        with _open_url(request, timeout=20) as source, destination.open("xb") as output:
            while True:
                chunk = source.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ARCHIVE or time.monotonic() > deadline:
                    raise ReleaseError("The release download exceeded its size/time limit. Existing files are unchanged.")
                digest.update(chunk)
                output.write(chunk)
    except ValueError:
        raise ReleaseError("GitHub returned an unsupported archive address. Existing files are unchanged.", "unsupported") from None
    except (OSError, urllib.error.URLError):
        raise ReleaseError("The release download failed. Existing files are unchanged; check your connection/free space and retry.", "offline") from None
    if digest.hexdigest() != candidate["archive_sha256"]:
        raise ReleaseError("The downloaded archive checksum does not match. Existing files are unchanged.")
