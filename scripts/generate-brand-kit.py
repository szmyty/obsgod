#!/usr/bin/env python3
"""Prepare an unapproved, content-bound Decky Stream review kit offline.

SVG/metadata preparation uses only Python's standard library. --raster requires
the exact Inkscape and DejaVu Sans pins in .identity/toolchain.lock.json. This is
not the Identity production compiler and never promotes candidates to approved.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "draft-manifest.json"
FONT_HASH = "57f73e11f51999432bf7ab22ce55b6f945d5eca1bf824404cfa9ec2e3718c84e"


def digest(content):
    return hashlib.sha256(content).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def source_inputs(root):
    paths = [*sorted((root / ".identity").rglob("*")), root / "scripts/generate-brand-kit.py",
             root / "branding/licenses/DejaVu.txt"]
    result = {}
    for path in paths:
        if path.is_symlink():
            raise ValueError("Brand input cannot be a symlink: " + str(path))
        if path.is_file():
            result[path.relative_to(root).as_posix()] = path.read_bytes()
    return result


def safe_svg(content):
    document = ET.fromstring(content)
    for node in document.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag not in {"svg", "title", "desc", "rect", "path"}:
            raise ValueError("Unexpected candidate SVG element: " + tag)
        for name, value in node.attrib.items():
            if name.lower().startswith("on") or name.rsplit("}", 1)[-1] in {"href", "style"} or "url(" in value:
                raise ValueError("Candidate SVG must be self-contained geometry")


def svg_document(width, height, title, body):
    # Keep editable text usable on GitHub/consumer machines without this font.
    # PNGs still render with the exact locked face; these are not outline masters.
    body = body.replace('font-family="DejaVu Sans"', 'font-family="DejaVu Sans,Arial,sans-serif"')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}" role="img" aria-labelledby="title desc">\n'
            f'<title id="title">{html.escape(title)}</title><desc id="desc">'
            'Proposed Decky Stream branding; human creative and rights approval pending.</desc>\n'
            f'{body}\n</svg>\n').encode()


def contrast(a, b):
    def luminance(color):
        values = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        values = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
        return sum(v * w for v, w in zip(values, (.2126, .7152, .0722)))
    values = sorted((luminance(a), luminance(b)))
    return round((values[1] + .05) / (values[0] + .05), 3)


def rasterize(files, lock):
    executable = shutil.which("inkscape")
    if not executable:
        raise ValueError("--raster requires the pinned Inkscape; SVG preparation works without it")
    version = subprocess.check_output([executable, "--version"], text=True).strip()
    if version != lock["draftExporter"]["rasterizerVersion"]:
        raise ValueError("Inkscape differs from the draft toolchain pin: " + version)
    font = Path(subprocess.check_output(["fc-match", "-f", "%{file}", "DejaVu Sans"], text=True))
    if digest(font.read_bytes()) != lock["draftExporter"]["fontSha256"]:
        raise ValueError("DejaVu Sans differs from the reviewed font pin")
    dimensions = {"web/favicon-16.png": ("masters/mark.svg", 16),
                  "web/favicon-32.png": ("masters/mark.svg", 32),
                  "web/favicon-64.png": ("masters/mark.svg", 64),
                  "masters/mark-transparent.png": ("masters/mark-transparent.svg", 512),
                  "docs/mark-64.png": ("masters/mark.svg", 64),
                  "github/avatar-256.png": ("masters/mark.svg", 256),
                  "github/avatar-512.png": ("masters/mark.svg", 512),
                  "docs/wordmark.png": ("docs/wordmark.svg", 720),
                  "github/social-preview.png": ("github/social-preview.svg", 1280),
                  "github/readme-header.png": ("github/readme-header.svg", 1600),
                  "github/readme-header-light.png": ("github/readme-header-light.svg", 1600),
                  "review/legibility-sheet.png": ("review/legibility-sheet.svg", 720)}
    with tempfile.TemporaryDirectory(prefix="decky-stream-brand-") as temporary:
        base = Path(temporary)
        for target, (source, width) in dimensions.items():
            input_path, output_path = base / "source.svg", base / "output.png"
            input_path.write_bytes(files[source])
            subprocess.run([executable, str(input_path), "--export-area-page", "--export-width=" + str(width),
                            "--export-filename=" + str(output_path)], check=True, capture_output=True)
            files[target] = output_path.read_bytes()
    validate_raster(files)
    return {"inkscape": version, "font_sha256": digest(font.read_bytes())}


def validate_raster(files):
    # Match the selected native v1 web/GitHub dimensions without claiming that
    # this local draft projection is approved output of Identity's compiler.
    expected = {"web/favicon-32.png": (32, 32), "web/favicon-64.png": (64, 64),
                "github/social-preview.png": (1280, 640),
                "github/readme-header.png": (1600, 600),
                "github/readme-header-light.png": (1600, 600)}
    for name, dimensions in expected.items():
        data = files[name]
        if data[:8] != b"\x89PNG\r\n\x1a\n" or len(data) < 24:
            raise ValueError("Invalid raster output: " + name)
        if struct.unpack(">II", data[16:24]) != dimensions:
            raise ValueError("Unexpected raster dimensions: " + name)
    if len(files["github/social-preview.png"]) > 999999:
        raise ValueError("GitHub preview exceeds the native v1 999999-byte limit")


def render(root=ROOT, raster=False):
    inputs = source_inputs(root)
    lock = json.loads(inputs[".identity/toolchain.lock.json"])
    inventory = json.loads(inputs[".identity/candidates/inventory.json"])
    if inventory.get("status") != "proposed-unapproved" or any(a.get("humanApproval") is not None for a in inventory["assets"]):
        raise ValueError("Draft preparer only accepts explicitly unapproved candidates")
    approvals = json.loads(inputs[".identity/governance/approvals.json"])
    if approvals["decisions"]:
        raise ValueError("Use the approved Identity pipeline after human decisions exist")
    mark, icon = inputs[".identity/candidates/mark.svg"], inputs[".identity/candidates/decky-icon.svg"]
    safe_svg(mark)
    safe_svg(icon)
    name = inventory["project"]["displayName"]
    if name != "Decky Stream" or inventory["project"]["id"] != "decky-stream":
        raise ValueError("Review the kit generator when the intended identity changes")
    colors = json.loads(inputs[".identity/candidates/palette.json"])["colors"]
    if any(not re.fullmatch(r"#[0-9a-f]{6}", value) for value in colors.values()):
        raise ValueError("Candidate colors must be opaque hexadecimal sRGB values")
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    def geometry_from(content, transparent=False, light=False):
        children = []
        for child in ET.fromstring(content):
            tag = child.tag.rsplit("}", 1)[-1]
            if tag in {"title", "desc"}:
                continue
            background = (tag == "rect" and child.get("width") == "128"
                          and child.get("height") == "128" and child.get("fill") == colors["ink"])
            if transparent and background:
                continue
            if light:
                for node in child.iter():
                    for attribute in ("fill", "stroke"):
                        value = node.get(attribute)
                        if value == colors["accent"]:
                            node.set(attribute, colors["ink"])
                        elif value == colors["ink"]:
                            node.set(attribute, colors["text"])
            children.append(ET.tostring(child, encoding="unicode"))
        return "".join(children)
    geometry = geometry_from(mark)
    icon_geometry = geometry_from(icon).replace("currentColor", "#eef4fc")
    wordmark = f'<g transform="translate(8 16) scale(.75)">{geometry}</g><text x="126" y="83" font-family="DejaVu Sans" font-size="46" font-weight="normal" fill="#eef4fc">Decky Stream</text>'

    def banner(width, height, light=False):
        background, foreground, muted = ((colors["text"], colors["ink"], "#37465a") if light else
                                          (colors["ink"], colors["text"], colors["muted"]))
        accent = colors["ink"] if light else colors["accent"]
        is_header = width == 1600
        body = f'<rect width="{width}" height="{height}" fill="{background}"/>'
        # Decorative broadcast arcs stay outside the text field. The mark and
        # copy remain useful when this ornament is cropped by a host platform.
        body += (f'<path d="M{width-180} -60Q{width+180} {height/2} {width-180} {height+60}" '
                 f'fill="none" stroke="{accent}" stroke-opacity=".10" stroke-width="64"/>'
                 f'<path d="M{width-70} -60Q{width+290} {height/2} {width-70} {height+60}" '
                 f'fill="none" stroke="{accent}" stroke-opacity=".07" stroke-width="64"/>')
        selected_geometry = geometry_from(mark, light=light)
        if is_header:
            body += (f'<g transform="translate(104 160) scale(2)">{selected_geometry}</g>'
                     f'<text x="416" y="260" font-family="DejaVu Sans" font-size="92" font-weight="bold" fill="{foreground}">Decky Stream</text>'
                     f'<text x="422" y="339" font-family="DejaVu Sans" font-size="38" fill="{accent}">Your game. Your stream.</text>'
                     f'<text x="422" y="398" font-family="DejaVu Sans" font-size="25" fill="{muted}">Stream from Steam Deck with OBS</text>'
                     f'<text x="108" y="530" font-family="DejaVu Sans" font-size="18" letter-spacing="3" fill="{muted}">LOCAL OBS CONTROL · STEAM DECK</text>')
        else:
            body += (f'<g transform="translate(88 76) scale(1.25)">{selected_geometry}</g>'
                     f'<text x="88" y="366" font-family="DejaVu Sans" font-size="78" font-weight="bold" fill="{foreground}">Decky Stream</text>'
                     f'<text x="92" y="438" font-family="DejaVu Sans" font-size="36" fill="{accent}">Your game. Your stream.</text>'
                     f'<text x="92" y="500" font-family="DejaVu Sans" font-size="27" fill="{muted}">Stream from Steam Deck with OBS</text>')
        return svg_document(width, height, name + " proposed " + ("README header" if is_header else "repository preview"), body)

    files = {"masters/mark.svg": mark, "decky/icon-monochrome.svg": icon,
             "masters/mark-transparent.svg": svg_document(128, 128, name + " proposed transparent mark", geometry_from(mark, transparent=True)),
             "masters/mark-on-light.svg": svg_document(128, 128, name + " proposed mark on light", geometry_from(mark, light=True)),
             "web/favicon.svg": mark,
             "docs/wordmark.svg": svg_document(480, 128, name + " proposed wordmark", wordmark),
             "github/social-preview.svg": banner(1280, 640),
             "github/readme-header.svg": banner(1600, 600),
             "github/readme-header-light.svg": banner(1600, 600, light=True),
             "tokens/palette.json": inputs[".identity/candidates/palette.json"],
             "metadata/project.json": encoded(inventory["project"]),
             "metadata/rights-and-sources.json": encoded(inventory),
             "licenses/DejaVu.txt": inputs["branding/licenses/DejaVu.txt"]}
    files["tokens/palette.css"] = (":root{" + ";".join("--draft-" + k + ":" + v for k, v in colors.items()) + "}\n").encode()
    sheet = '<rect width="720" height="400" fill="#111c2a"/><text x="24" y="40" font-family="DejaVu Sans" font-size="20" fill="#eef4fc">Draft mark: inspect at actual size</text>'
    x = 28
    for size in (16, 24, 32, 64, 128):
        sheet += f'<g transform="translate({x} 80) scale({size / 128})">{geometry}</g><text x="{x}" y="250" font-family="DejaVu Sans" font-size="14" fill="#b7c5d8">{size}px</text>'
        x += size + 42
    sheet += '<text x="24" y="300" font-family="DejaVu Sans" font-size="20" fill="#eef4fc">Native Decky foreground: 16 / 24 / 32px</text>'
    for x, size in ((28, 16), (90, 24), (164, 32)):
        sheet += f'<g transform="translate({x} 330) scale({size / 24})">{icon_geometry}</g>'
    files["review/legibility-sheet.svg"] = svg_document(720, 400, "Proposed mark size sheet", sheet)
    pairs = {"body_on_ink": ("text", "ink"), "muted_on_ink": ("muted", "ink"),
             "accent_on_ink": ("accent", "ink"), "button_label_on_accent": ("accentInk", "accent")}
    ratios = {key: contrast(colors[a], colors[b]) for key, (a, b) in pairs.items()}
    files["review/contrast.json"] = encoded({"method": "WCAG sRGB relative luminance", "minimum_normal_text": 4.5,
        "ratios": ratios, "automated_status": "passed" if min(ratios.values()) >= 4.5 else "failed",
        "human_legibility": "unrun; inspect 16/24/32px in native Decky at actual device size",
        "state": "Brand colors are decorative; status must use text plus observed state, not color alone"})
    if min(ratios.values()) < 4.5:
        raise ValueError("Candidate palette failed normal-text contrast")
    files["README.md"] = ("# Proposed Decky Stream kit\n\nHuman creative and rights approval is pending. Do not install as production branding.\n\n"
        "SVG masters are editable; PNGs, when present, use the locked Inkscape/font. Native Decky uses its theme and a monochrome icon. "
        "A quarter-mark clear space and 16px draft minimum are proposals requiring actual device review. "
        "No animation, third-party logos, final organization, trademark clearance or publication is implied. "
        "The wordmark uses DejaVu Sans; see licenses/DejaVu.txt. Mark geometry was AI-assisted original work by OpenAI Codex for this repository. "
        "Owner must decide rights/license before production adoption. See metadata/rights-and-sources.json.\n\n"
        "Run python3 scripts/generate-brand-kit.py --raster --check with the same toolchain for drift verification. "
        "Delete only a known generated kit directory to rebuild after a source change; do not change manifest hashes by hand.\n").encode()
    files["review/index.html"] = b'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Proposed Decky Stream kit</title><link rel="stylesheet" href="review.css"></head><body><main><h1>Decky Stream: proposed brand</h1><p>Human creative and rights review pending. Live product icon and theme are unchanged.</p><img class="wordmark" src="../docs/wordmark.svg" alt="Proposed Decky Stream wordmark"><h2>Actual-size geometry</h2><img class="sheet" src="legibility-sheet.svg" alt="Proposed play-and-transmission mark at 16, 24, 32, 64 and 128 pixels"><h2>README header</h2><img class="social" src="../github/readme-header.svg" alt="Proposed Decky Stream README header"><h2>Light README header</h2><img class="social" src="../github/readme-header-light.svg" alt="Proposed Decky Stream README header on a light field"><h2>Repository preview</h2><img class="social" src="../github/social-preview.svg" alt="Proposed Decky Stream social preview"><p>These images are candidates, not approved product branding. Check the README, rights inventory, contrast report and manifest before review. SVG text uses DejaVu Sans. No animation or remote assets.</p></main></body></html>\n'
    files["review/review.css"] = b':root{color-scheme:dark;font-family:system-ui,sans-serif}body{margin:0;background:#111c2a;color:#eef4fc;line-height:1.6}main{max-width:1000px;margin:auto;padding:24px}img{max-width:100%;height:auto}.wordmark{width:480px}.sheet{width:720px}.social{width:800px}h1{font-size:2rem}p{max-width:70ch;color:#b7c5d8}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}\n'
    toolchain = rasterize(files, lock) if raster else {"raster": "unrun; pass --raster with the locked tools"}
    sources = {p: digest(data) for p, data in inputs.items()}
    manifest = {"schema": "decky-stream.draft-brand-kit/v1", "approval": "proposed-unapproved",
        "identity_revision": lock["revision"], "generator": "local draft preparer; not Identity compiler",
        "source_sha256": digest(encoded(sources)), "sources": sources, "toolchain": toolchain,
        "outputs": {p: {"sha256": digest(data), "bytes": len(data)} for p, data in sorted(files.items())},
        "gates": ["owner creative/rights/license approval", "organization and repository decision", "native Deck legibility/controller receipt", "approved Identity production generation and drift check", "publication approval"]}
    files[MANIFEST] = encoded(manifest)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path, data in sorted(files.items()):
            info = zipfile.ZipInfo("decky-stream-proposed/" + path, (1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(info, data)
    files["decky-stream-proposed.zip"] = archive.getvalue()
    return files


def repository_assets(files):
    """A bounded draft projection for tracked repository presentation assets."""
    mapping = {
        "header.svg": "github/readme-header.svg",
        "header-light.svg": "github/readme-header-light.svg",
        "header.png": "github/readme-header.png",
        "header-light.png": "github/readme-header-light.png",
        "logo.svg": "masters/mark.svg",
        "logo-transparent.svg": "masters/mark-transparent.svg",
        "logo-transparent.png": "masters/mark-transparent.png",
        "logo-light.svg": "masters/mark-on-light.svg",
        "wordmark.svg": "docs/wordmark.svg",
        "wordmark.png": "docs/wordmark.png",
        "icon-monochrome.svg": "decky/icon-monochrome.svg",
        "favicon.svg": "web/favicon.svg",
        "favicon-16.png": "web/favicon-16.png",
        "favicon-32.png": "web/favicon-32.png",
        "favicon-64.png": "web/favicon-64.png",
        "avatar-256.png": "github/avatar-256.png",
        "avatar-512.png": "github/avatar-512.png",
        "social-preview.svg": "github/social-preview.svg",
        "social-preview.png": "github/social-preview.png",
        "palette.json": "tokens/palette.json",
        "palette.css": "tokens/palette.css",
        "asset-sources.json": "metadata/rights-and-sources.json",
        "font-LICENSE.txt": "licenses/DejaVu.txt",
        "legibility-sheet.svg": "review/legibility-sheet.svg",
        "legibility-sheet.png": "review/legibility-sheet.png",
        "contrast.json": "review/contrast.json",
    }
    selected = {target: files[source] for target, source in mapping.items() if source in files}
    selected["README.md"] = (
        "# Decky Stream repository artwork — draft\n\n"
        "These are review candidates, not approved production branding or a live plugin replacement. "
        "Editable masters, actual generation methods and unresolved rights facts live in `.identity/candidates/`. "
        "The image-generation concept board is a reference; these SVG/PNG exports are generated from the editable SVG master.\n\n"
        "The selected native Identity v1 web/GitHub dimensions inform the favicon and 1280×640 preview. "
        "README headers, avatars, wordmark, transparent/light variants and native Decky monochrome icon "
        "are product-specific draft exports, not native v1 profile outputs. Native `docs` produces document CSS. "
        "This local exporter is not Identity's production compiler. No PWA or generic social profile is claimed.\n\n"
        "Regenerate with `python3 scripts/generate-brand-kit.py --raster --repository-assets`; "
        "append `--check` for read-only drift verification. The exact Inkscape and DejaVu Sans pins "
        "are in `.identity/toolchain.lock.json`; the separate font notice is `font-LICENSE.txt`. "
        "No font binary is redistributed. The manifest binds source and output bytes but is not human approval or a signature.\n"
    ).encode()
    manifest = json.loads(files[MANIFEST])
    manifest["projection"] = "tracked repository review assets; not approved native Identity output"
    manifest["outputs"] = {p: {"sha256": digest(data), "bytes": len(data)} for p, data in sorted(selected.items())}
    selected[MANIFEST] = encoded(manifest)
    return selected


def write_or_check(files, output, check=False):
    output = output.absolute()
    # Walk every ancestor before resolve; even an empty symlink destination is unsafe.
    if any(path.is_symlink() for path in (output, *output.parents)):
        raise ValueError("Output must not traverse symlinks")
    if output.exists() and not output.is_dir():
        raise ValueError("Output is not a directory")
    existing = set()
    if output.exists():
        for path in output.rglob("*"):
            if path.is_symlink():
                raise ValueError("Generated output contains a symlink")
            if path.is_file():
                existing.add(path.relative_to(output).as_posix())
        if existing:
            if MANIFEST not in existing:
                raise ValueError("Refusing to replace unrelated files")
            previous = json.loads((output / MANIFEST).read_text())
            if previous.get("schema") != "decky-stream.draft-brand-kit/v1":
                raise ValueError("Unrecognized output manifest")
            owned = set(previous.get("outputs", {})) | {MANIFEST, "decky-stream-proposed.zip"}
            if existing - owned:
                raise ValueError("Unrelated files exist in output")
    if check:
        if existing != set(files) or any((output / p).read_bytes() != data for p, data in files.items()):
            raise ValueError("Draft kit drift detected; rebuild from reviewed sources")
        return
    for path in existing - set(files):
        (output / path).unlink()
    for path, data in files.items():
        target = output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Full kit destination; defaults to dist/branding-draft")
    parser.add_argument("--raster", action="store_true", help="Include PNG exports using exact locked tools")
    parser.add_argument("--repository-assets", action="store_true",
                        help="Stage only the bounded review projection in branding/repository")
    parser.add_argument("--check", action="store_true", help="Read-only exact output drift verification")
    args = parser.parse_args()
    try:
        if args.repository_assets and args.output is not None:
            raise ValueError("--repository-assets uses the fixed branding/repository destination, not --output")
        output = (ROOT / "branding/repository" if args.repository_assets else
                  args.output if args.output is not None else ROOT / "dist/branding-draft").absolute()
        if (not args.repository_assets and output.resolve().is_relative_to(ROOT)
                and not output.resolve().is_relative_to(ROOT / "dist")):
            raise ValueError("Generated kit must be in dist/ or outside the repository")
        files = render(raster=args.raster)
        if args.repository_assets:
            files = repository_assets(files)
        write_or_check(files, output, check=args.check)
    except (ValueError, OSError, ET.ParseError, subprocess.SubprocessError) as error:
        parser.error(str(error))
    print(json.dumps({"status": "verified" if args.check else "prepared", "approval": "proposed-unapproved",
                      "output": str(output), "files": len(files),
                      "manifest_sha256": digest(files[MANIFEST]),
                      "archive_sha256": digest(files["decky-stream-proposed.zip"]) if "decky-stream-proposed.zip" in files else None}))


if __name__ == "__main__":
    main()
