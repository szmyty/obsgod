#!/usr/bin/env python3
"""Export the selected aurora candidate from pinned sources, never old mint files.

This local review exporter is not Identity's production compiler. Raster exports
use the exact repository Inkscape/font pins. The original generated hero and
separately authored vector sources have distinct provenance and approval facts.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import html
import importlib.util
import json
import os
import stat
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "orbital-stream-aurora"
MANIFEST = "aurora-manifest.json"
SCHEMA = "deckystream.selected-brand-kit/v1"
SOURCE = ".identity/candidates/aurora/"
REFERENCES = {
    ".identity/candidates/concepts/orbital-stream-color-alternatives.png": "4e2076ce7ba139a97d1ecf3b730de6db0cb15d9452cfcefbd8885b2af7b9c801",
    ".identity/candidates/concepts/orbital-stream-board.png": "5301893b21e08872262cced4e6415e117ddf20900e0ee64e816f912b298c8a5e",
    ".identity/candidates/concepts/orbital-stream-gradient-icon.png": "4c59ae9c7716c3889bd837071b55cef0e8641419405ded250f8d73620eab5f49",
}
INPUT_PATHS = (
    *[SOURCE + name for name in ("mark.svg", "mark-small.svg", "palette.json", "inventory.json", "hero-master.png", "hero-generation.json")],
    *REFERENCES,
    *[name[:-4] + ".json" for name in REFERENCES],
    ".identity/candidates/concepts/selection.json", ".identity/toolchain.lock.json",
    ".identity/governance/approvals.json", ".identity/identity.json",
    "branding/licenses/DejaVu.txt", "scripts/generate-brand-kit.py", "scripts/generate-aurora-kit.py",
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def source_inputs(root):
    root = Path(root).absolute()
    result = {}
    for relative in INPUT_PATHS:
        path = root / relative
        if any(part.is_symlink() for part in (path, *path.parents)):
            raise ValueError("Aurora input traverses a symlink: " + relative)
        if not path.is_file():
            raise ValueError("Required aurora source is missing: " + relative)
        result[relative] = path.read_bytes()
    for relative, expected in REFERENCES.items():
        if digest(result[relative]) != expected:
            raise ValueError("Selected reference digest differs: " + relative)
        record = json.loads(result[relative[:-4] + ".json"])
        if record.get("sha256") != expected or record.get("path") != relative:
            raise ValueError("Selected reference record differs: " + relative)
    return result


def safe_svg(content):
    if len(content) > 65536 or b"<!" in content or b"<?" in content:
        raise ValueError("Unsupported SVG declaration or excessive source")
    document = ET.fromstring(content)
    tags = {"svg", "title", "desc", "defs", "linearGradient", "radialGradient", "stop", "g", "path", "rect", "circle", "ellipse", "filter", "feGaussianBlur"}
    ids = []
    references = []
    namespace = "{http://www.w3.org/2000/svg}"
    if document.tag != namespace + "svg":
        raise ValueError("Aurora root must be SVG in its standard namespace")
    for node in document.iter():
        if not isinstance(node.tag, str) or not node.tag.startswith(namespace):
            raise ValueError("Foreign SVG namespaces are not permitted")
        tag = node.tag.rsplit("}", 1)[-1]
        if tag not in tags:
            raise ValueError("Unexpected aurora SVG element: " + tag)
        if "id" in node.attrib:
            value = node.attrib["id"]
            if value in ids or not re.fullmatch(r"(?:aurora-[a-z0-9-]+|title|desc)", value):
                raise ValueError("Unsafe or duplicate aurora SVG id")
            ids.append(value)
        for name, value in node.attrib.items():
            if name.startswith("{"):
                raise ValueError("Foreign SVG attribute namespaces are not permitted")
            local = name.rsplit("}", 1)[-1].lower()
            if "\\" in value or "//" in value or local.startswith("on") or local in {"href", "style"} or any(marker in value.lower() for marker in ("javascript:", "http:", "https:", "data:")):
                raise ValueError("Aurora source must be self-contained safe geometry")
            if "url(" in value.lower():
                if not re.fullmatch(r"url\(#[a-z0-9-]+\)", value):
                    raise ValueError("Only local SVG references are permitted")
                references.append(value[5:-1])
    if any(reference not in ids for reference in references):
        raise ValueError("Unresolved local SVG reference")
    if document.get("viewBox") != "0 0 256 256":
        raise ValueError("Aurora geometry must retain its 256-unit view box")
    return document


def fragment(content, prefix):
    document = safe_svg(content)
    mapping = {node.get("id"): prefix + "-" + node.get("id") for node in document.iter() if node.get("id")}
    children = []
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    for original in document:
        if original.tag.rsplit("}", 1)[-1] in {"title", "desc"}:
            continue
        node = copy.deepcopy(original)
        for child in node.iter():
            for name, value in list(child.attrib.items()):
                if name == "id":
                    child.set(name, mapping[value])
                elif value.startswith("url(#"):
                    child.set(name, "url(#" + mapping[value[5:-1]] + ")")
        children.append(ET.tostring(node, encoding="unicode"))
    return "".join(children)


def svg(width, height, title, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-labelledby="title desc">'
            f'<title id="title">{html.escape(title)}</title><desc id="desc">Selected aurora candidate. Production rights and actual device acceptance remain pending; decorative color does not indicate stream state.</desc>{body}</svg>\n').encode()


def helpers(root):
    spec = importlib.util.spec_from_file_location("aurora_export_helpers", root / "scripts/generate-brand-kit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def png_dimensions(data):
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Expected an ordinary PNG")
    return struct.unpack(">II", data[16:24])


def rasterize(files, lock):
    executable = shutil.which("inkscape")
    if not executable:
        raise ValueError("Raster generation requires the pinned Inkscape")
    version = subprocess.check_output([executable, "--version"], text=True).strip()
    font = Path(subprocess.check_output(["fc-match", "-f", "%{file}", "DejaVu Sans"], text=True))
    if version != lock["draftExporter"]["rasterizerVersion"] or digest(font.read_bytes()) != lock["draftExporter"]["fontSha256"]:
        raise ValueError("Aurora raster tools differ from their pins")
    targets = {"masters/mark.png": ("masters/mark.svg", 512), "masters/mark-transparent.png": ("masters/mark-transparent.svg", 512),
               "masters/mark-on-light.png": ("masters/mark-on-light.svg", 512), "masters/mark-small.png": ("masters/mark-small.svg", 128),
               "docs/wordmark.png": ("docs/wordmark.svg", 960), "github/avatar-256.png": ("masters/mark.svg", 256),
               "github/avatar-512.png": ("masters/mark.svg", 512), "github/readme-header.png": ("github/readme-header.svg", 1600),
               "github/readme-header-light.png": ("github/readme-header-light.svg", 1600), "github/social-preview.png": ("github/social-preview.svg", 1280),
               "review/legibility-sheet.png": ("review/legibility-sheet.svg", 840), "review/menu-sheet.png": ("review/menu-sheet.svg", 840)}
    targets.update({f"web/favicon-{size}.png": ("masters/mark-small.svg", size) for size in (16, 24, 32, 64)})
    with tempfile.TemporaryDirectory(prefix="deckystream-aurora-") as temporary:
        base = Path(temporary)
        for target, (source, width) in targets.items():
            source_file, output_file = base / "input.svg", base / "output.png"
            source_file.write_bytes(files[source])
            subprocess.run([executable, str(source_file), "--export-area-page", "--export-width=" + str(width), "--export-filename=" + str(output_file)], check=True, capture_output=True)
            files[target] = output_file.read_bytes()
            if png_dimensions(files[target])[0] != width:
                raise ValueError("Unexpected raster width: " + target)
    for name, size in {"github/readme-header.png": (1600, 600), "github/readme-header-light.png": (1600, 600), "github/social-preview.png": (1280, 640)}.items():
        if png_dimensions(files[name]) != size:
            raise ValueError("Unexpected profile dimensions: " + name)
    if len(files["github/social-preview.png"]) > 999999:
        raise ValueError("GitHub preview exceeds its native v1 byte cap")
    return {"inkscape": version, "font_sha256": digest(font.read_bytes()), "raster_reproduction": "Pinned master exports; image generation itself is not claimed deterministic"}


def gallery(files):
    cards = []
    for name, data in sorted(files.items()):
        if not name.endswith(".png"):
            continue
        width, height = png_dimensions(data)
        uri = "data:image/png;base64," + base64.b64encode(data).decode()
        label = html.escape(name)
        cards.append(f'<article><div class="image"><img src="{uri}" width="{width}" height="{height}" alt="{label}"></div><h2>{label}</h2><p>{width} × {height} PNG</p><a href="{uri}" download="{html.escape(Path(name).name)}">Save ordinary PNG</a></article>')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>deckystream — aurora artwork</title><style>'
            ':root{font-family:system-ui,sans-serif;color:#edf9fc;background:#050b14;color-scheme:dark}body{margin:0}main{max-width:1200px;margin:auto;padding:28px}h1{font-size:2.4rem}p{max-width:78ch;line-height:1.6;color:#abc2d4}a{color:#8df9ff}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:20px}article{min-width:0;border:1px solid #334b60;border-radius:16px;padding:16px;background:#101d2a}h2{font-size:1rem;overflow-wrap:anywhere}.image{height:230px;display:flex;align-items:center;justify-content:center;background:#08111e}.image img{max-width:100%;max-height:100%;object-fit:contain;width:auto;height:auto}.note{border-left:3px solid #b4a1f3;padding:12px 20px}code{overflow-wrap:anywhere}</style></head><body><main>'
            '<h1>deckystream · aurora</h1><p>Selected 01 / aurora direction, exported as review candidates. This single page works offline: images are embedded and no remote fonts, scripts, trackers or assets are used.</p>'
            '<p class="note">These are artwork previews, not a live plugin screenshot or installer. Creative direction is selected; final rights/licensing, production adoption and actual Steam Deck review remain separate.</p>'
            '<h2>What to open</h2><p>PNG files are ordinary images for a browser or photo viewer. Extract <code>deckystream-aurora-png.zip</code> first. SVG files are editable vectors; JSON/CSS are metadata, not photographs. Transparent gradients are intended for a dark field. The light mark includes a deliberate dark inset plate so its gradient stays recognizable on a light page. The compact mark omits glow at small sizes. Monochrome is an optional fallback, not a Decky requirement.</p>'
            '<div class="grid">' + ("".join(cards) or '<p>Raster export is unrun; use the pinned tools with --raster to include PNG previews.</p>') + '</div></main></body></html>\n').encode()


def render(root=ROOT, raster=False):
    root = Path(root).absolute()
    inputs = source_inputs(root)
    lock = json.loads(inputs[".identity/toolchain.lock.json"])
    inventory = json.loads(inputs[SOURCE + "inventory.json"])
    selected = json.loads(inputs[".identity/candidates/concepts/selection.json"])
    if inventory.get("profile") != PROFILE or inventory.get("status") != "proposed-unapproved" or any(asset.get("humanApproval") is not None for asset in inventory["assets"]):
        raise ValueError("Aurora exporter accepts only its unapproved production candidates")
    if selected.get("id") != PROFILE or selected["selectedPrimary"]["variantNumber"] != "01" or selected["selectedPrimary"]["variantName"] != "aurora":
        raise ValueError("Aurora source no longer matches the selected direction")
    if json.loads(inputs[".identity/governance/approvals.json"])["decisions"]:
        raise ValueError("Candidate exporter cannot invent or consume production approvals")
    if inventory["project"]["id"] != "decky-stream" or inventory["project"]["displayName"] != "deckystream":
        raise ValueError("Stable brand ID and selected lowercase display must remain explicit")
    for asset in inventory["assets"]:
        if asset["path"] not in inputs or digest(inputs[asset["path"]]) != asset["sha256"]:
            raise ValueError("Declared selected asset digest differs: " + asset["path"])
    hero_record = json.loads(inputs[SOURCE + "hero-generation.json"])
    hero = inputs[SOURCE + "hero-master.png"]
    if digest(hero) != hero_record["artifact"]["sha256"] or png_dimensions(hero) != (2048, 768):
        raise ValueError("Original hero raster master differs")
    colors = json.loads(inputs[SOURCE + "palette.json"])["colors"]
    if any(not re.fullmatch(r"#[0-9a-f]{6}", value) for value in colors.values()):
        raise ValueError("Palette values must be opaque sRGB hex")
    mark, small = inputs[SOURCE + "mark.svg"], inputs[SOURCE + "mark-small.svg"]
    safe_svg(mark); safe_svg(small)
    helper = helpers(root)
    def placement(source, prefix, x=0, y=0, size=256):
        return f'<g transform="translate({x} {y}) scale({size / 256})">{fragment(source, prefix)}</g>'
    def text(value, x, y, size, color, spacing=0, weight="normal"):
        return f'<text x="{x}" y="{y}" font-family="DejaVu Sans,Arial,sans-serif" font-size="{size}" font-weight="{weight}" letter-spacing="{spacing}" fill="{color}">{html.escape(value)}</text>'
    dark = f'<rect width="256" height="256" fill="{colors["ink"]}"/>' + placement(mark, "dark")
    light = f'<rect width="256" height="256" fill="{colors["light"]}"/><rect x="8" y="8" width="240" height="240" rx="48" fill="{colors["ink"]}"/>' + placement(mark, "light")
    hero_uri = "data:image/png;base64," + base64.b64encode(hero).decode()
    header = f'<image href="{hero_uri}" x="0" y="0" width="1600" height="600"/>' + text("deckystream", 100, 255, 86, colors["text"], 5) + text("your game. your stream.", 107, 322, 28, colors["text"], 6) + text("local OBS control for Steam Deck", 108, 520, 20, colors["muted"], 2)
    header_light = f'<rect width="1600" height="600" fill="{colors["light"]}"/><rect x="1090" y="55" width="470" height="470" rx="70" fill="{colors["ink"]}"/>' + placement(mark, "light-header", 1110, 75, 430) + text("deckystream", 104, 262, 86, colors["lightText"], 4) + text("your game. your stream.", 110, 330, 28, colors["lightText"], 5) + text("local OBS control for Steam Deck", 110, 520, 20, colors["lightText"], 2)
    preview = f'<rect width="1280" height="640" fill="{colors["ink"]}"/>' + placement(mark, "social", 830, 100, 350) + text("deckystream", 90, 285, 76, colors["text"], 3) + text("your game. your stream.", 96, 350, 27, colors["muted"], 3) + text("local OBS control · Steam Deck", 96, 565, 20, colors["aqua"], 2)
    wordmark = placement(mark, "wordmark", 0, 0, 128) + text("deckystream", 155, 88, 62, colors["text"], 2)
    sheet = f'<rect width="840" height="440" fill="{colors["ink"]}"/>' + text("aurora · actual-size compact exports", 24, 35, 22, colors["text"])
    x = 32
    for size in (16, 24, 32, 64, 128):
        sheet += placement(small, "size-" + str(size), x, 85, size) + text(str(size) + "px", x, 250, 15, colors["muted"])
        x += size + 65
    sheet += text("Transparent compact mark; no glow. Inspect at 100% zoom.", 24, 340, 18, colors["muted"]) + text("Color is decorative. Actual Deck/controller acceptance remains unrun.", 24, 380, 17, colors["muted"])
    menu = f'<rect width="840" height="520" fill="{colors["ink"]}"/>' + text("dark / highlighted menu · actual sizes", 24, 35, 22, colors["text"])
    for row, fill in enumerate((colors["surface"], colors["focus"])):
        for i, size in enumerate((16, 24, 32, 64)):
            x, y = 24 + i * 200, 80 + row * 185
            menu += f'<rect x="{x}" y="{y}" width="182" height="150" rx="12" fill="{fill}"/>' + placement(small, f"menu-{row}-{size}", x + 16, y + 20, size) + text(str(size) + "px", x + 16, y + 125, 17, colors["text"])
    menu += text("Static menu samples, not a Steam Deck screenshot or device receipt.", 24, 490, 17, colors["muted"])
    files = {"masters/mark.svg": svg(256, 256, "deckystream aurora on dark", dark), "masters/mark-transparent.svg": mark,
             "masters/mark-on-light.svg": svg(256, 256, "deckystream aurora on light", light), "masters/mark-small.svg": small,
             "web/favicon.svg": small, "docs/wordmark.svg": svg(760, 128, "deckystream lowercase wordmark", wordmark),
             "github/readme-header.svg": svg(1600, 600, "deckystream aurora hero", header), "github/readme-header-light.svg": svg(1600, 600, "deckystream light header", header_light),
             "github/social-preview.svg": svg(1280, 640, "deckystream repository preview", preview), "review/legibility-sheet.svg": svg(840, 440, "aurora actual-size sheet", sheet),
             "review/menu-sheet.svg": svg(840, 520, "aurora dark and focused menu samples", menu), "tokens/palette.json": inputs[SOURCE + "palette.json"],
             "metadata/rights-and-sources.json": encoded(inventory), "metadata/hero-generation.json": inputs[SOURCE + "hero-generation.json"], "licenses/DejaVu.txt": inputs["branding/licenses/DejaVu.txt"]}
    pairs = {"body_on_ink": ("text", "ink"), "muted_on_ink": ("muted", "ink"), "light_text_on_light": ("lightText", "light"), "focused_label": ("text", "focus")}
    ratios = {key: helper.contrast(colors[a], colors[b]) for key, (a, b) in pairs.items()}
    if min(ratios.values()) < 4.5:
        raise ValueError("Candidate text contrast is below 4.5:1")
    files["review/contrast.json"] = encoded({"method": "WCAG sRGB relative luminance", "text_ratios": ratios, "minimum_normal_text": 4.5, "decorative_gradient": "Not a status indicator; inspect actual-size sheets and target rendering separately", "actual_device": "unrun"})
    files["tokens/palette.css"] = (":root{" + ";".join("--aurora-" + key + ":" + value for key, value in colors.items()) + "}\n").encode()
    files["README.md"] = ("# deckystream · selected aurora candidate\n\nOpen index.html for the standalone offline gallery. Extract deckystream-aurora-png.zip for ordinary PNG images. Transparent marks/wordmarks need a dark field; the light mark has a deliberate dark inset plate. The compact mark removes glow for small presentation. Monochrome is optional, not a Decky platform requirement.\n\nThe raster hero is one preserved image_gen output; vector geometry is separately authored by OpenAI Codex from the selected direction and is not an identical conversion. Exact source and output hashes are in aurora-manifest.json. Neither reproducible exports nor direction selection establish final rights/license, organization, publisher or actual device adoption. No approved Identity compiler, release or migration is claimed. The font notice is licenses/DejaVu.txt; no font binary is redistributed.\n\nRegenerate with python3 scripts/generate-aurora-kit.py --raster; append --check for read-only drift verification. Old mint files/receipts are separate historical preparation and are never overwritten by this profile.\n").encode()
    toolchain = rasterize(files, lock) if raster else {"raster": "unrun"}
    files["index.html"] = gallery(files)
    if raster:
        previews = {Path(path).name: data for path, data in files.items() if path.endswith(".png")}
        if len(previews) != sum(path.endswith(".png") for path in files):
            raise ValueError("PNG download names collide")
        previews["START-HERE.txt"] = b"deckystream aurora PNG previews\n\nExtract this ZIP. Every PNG is an ordinary image. Start with readme-header.png. Transparent marks and the pale wordmark need a dark background; mark-on-light.png contains a dark inset plate for use on light pages. Favicons are intentionally tiny. SVG/JSON/CSS are editable source/metadata, not photo formats. These are review candidates; final rights and actual device acceptance remain separate.\n"
        files["deckystream-aurora-png.zip"] = helper.deterministic_zip(previews, "deckystream-aurora-png")
    sources = {path: digest(data) for path, data in inputs.items()}
    files[MANIFEST] = encoded({"schema": SCHEMA, "profile": PROFILE, "approval": "proposed-unapproved", "status": "selected-direction; unapproved-production-candidate", "identity_revision": lock["revision"], "sources": sources, "source_sha256": digest(encoded(sources)), "toolchain": toolchain, "outputs": {path: {"sha256": digest(data), "bytes": len(data)} for path, data in sorted(files.items())}, "limits": ["Candidate exports, not approved Identity compiler output", "Image generation is not deterministic; downstream exports are pinned to its unchanged source", "Final rights, owner/publisher and target adoption remain explicit", "Decorative color does not establish observed stream state"]})
    files["deckystream-aurora-kit.zip"] = helper.deterministic_zip(files, "deckystream-aurora-kit")
    return files


def write_or_check(files, output, check=False):
    for relative, data in files.items():
        if not isinstance(relative, str) or not relative or "\x00" in relative or relative.startswith("/") or ".." in Path(relative).parts or not isinstance(data, bytes):
            raise ValueError("Unsafe generated path or payload")
    output = Path(output).absolute()
    if any(path.is_symlink() for path in (output, *output.parents)):
        raise ValueError("Aurora output must not traverse a symlink")
    if ".." in output.parts or output.name in {"repository", ".identity", "candidates", "sources"}:
        raise ValueError("Aurora profile cannot replace historical or source directories")
    if output.exists() and not output.is_dir():
        raise ValueError("Aurora output is not a directory")
    existing = set()
    if output.exists():
        for path in output.rglob("*"):
            if path.is_symlink():
                raise ValueError("Aurora output contains a symlink")
            info = path.lstat()
            if stat.S_ISREG(info.st_mode):
                if info.st_nlink != 1:
                    raise ValueError("Aurora output must not contain hardlinked files")
                existing.add(path.relative_to(output).as_posix())
            elif not stat.S_ISDIR(info.st_mode):
                raise ValueError("Aurora output contains a nonregular node")
        if existing:
            if MANIFEST not in existing:
                raise ValueError("Refusing unrelated or historical output")
            previous = json.loads((output / MANIFEST).read_bytes())
            if previous.get("schema") != SCHEMA or previous.get("profile") != PROFILE:
                raise ValueError("Aurora output belongs to a different profile")
            owned = set(previous.get("outputs", {})) | {MANIFEST, "deckystream-aurora-kit.zip"}
            if existing - owned:
                raise ValueError("Unrelated files exist in aurora output")
    if check:
        if existing != set(files) or any((output / path).read_bytes() != data for path, data in files.items()):
            raise ValueError("Aurora output drift detected")
        return
    for path in existing - set(files):
        (output / path).unlink()
    for path, data in files.items():
        if path.startswith("/") or ".." in Path(path).parts:
            raise ValueError("Unsafe generated path")
        target = output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".aurora-export-", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                os.fchmod(stream.fileno(), 0o644)
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=ROOT, help="Source root; the profile uses only its explicit source allowlist")
    parser.add_argument("--output", type=Path, help="Defaults to branding/aurora; historical mint directories are forbidden")
    parser.add_argument("--raster", action="store_true", help="Include ordinary PNGs using exact pinned Inkscape/font")
    parser.add_argument("--check", action="store_true", help="Read-only exact source/output drift verification")
    args = parser.parse_args()
    try:
        root = args.repository_root.absolute()
        output = args.output.absolute() if args.output is not None else root / "branding/aurora"
        if output == root or output in root.parents or output == root / "branding" or any(output == root / source or root / source in output.parents for source in (".identity", "scripts", "steamdeck", "site", "branding/repository")):
            raise ValueError("Output cannot replace source, runtime or historical mint trees")
        files = render(root, args.raster)
        write_or_check(files, output, args.check)
        print(json.dumps({"profile": PROFILE, "status": "checked" if args.check else "generated", "files": len(files), "output": str(output), "production_approval": "not claimed"}, sort_keys=True))
    except (ValueError, KeyError, OSError, ET.ParseError, subprocess.CalledProcessError) as error:
        parser.exit(1, "Aurora export refused: " + str(error) + "\n")


if __name__ == "__main__":
    main()
