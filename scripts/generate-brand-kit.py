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
                  "docs/mark-64.png": ("masters/mark.svg", 64),
                  "github/avatar-256.png": ("masters/mark.svg", 256),
                  "github/avatar-512.png": ("masters/mark.svg", 512),
                  "docs/wordmark.png": ("docs/wordmark.svg", 720),
                  "github/social-preview.png": ("github/social-preview.svg", 1280),
                  "review/legibility-sheet.png": ("review/legibility-sheet.svg", 720)}
    with tempfile.TemporaryDirectory(prefix="decky-stream-brand-") as temporary:
        base = Path(temporary)
        for target, (source, width) in dimensions.items():
            input_path, output_path = base / "source.svg", base / "output.png"
            input_path.write_bytes(files[source])
            subprocess.run([executable, str(input_path), "--export-area-page", "--export-width=" + str(width),
                            "--export-filename=" + str(output_path)], check=True, capture_output=True)
            files[target] = output_path.read_bytes()
    return {"inkscape": version, "font_sha256": digest(font.read_bytes())}


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
    def geometry_from(content):
        return "".join(ET.tostring(child, encoding="unicode") for child in ET.fromstring(content)
                       if child.tag.rsplit("}", 1)[-1] not in {"title", "desc"})
    geometry = geometry_from(mark)
    icon_geometry = geometry_from(icon).replace("currentColor", "#eef4fc")
    wordmark = f'<g transform="translate(8 16) scale(.75)">{geometry}</g><text x="126" y="83" font-family="DejaVu Sans" font-size="46" font-weight="normal" fill="#eef4fc">Decky Stream</text>'
    files = {"masters/mark.svg": mark, "decky/icon-monochrome.svg": icon,
             "web/favicon.svg": mark,
             "docs/wordmark.svg": svg_document(480, 128, name + " proposed wordmark", wordmark),
             "github/social-preview.svg": svg_document(1280, 640, name + " proposed repository preview",
                 '<rect width="1280" height="640" fill="#0b111b"/>'
                 f'<g transform="translate(96 112) scale(1.5)">{geometry}</g>'
                 '<text x="96" y="394" font-family="DejaVu Sans" font-size="76" fill="#eef4fc">Decky Stream</text>'
                 '<text x="100" y="456" font-family="DejaVu Sans" font-size="30" fill="#b7c5d8">Stream from Steam Deck with OBS</text>'
                 '<text x="100" y="568" font-family="DejaVu Sans" font-size="22" fill="#b2f2c7">PROPOSED BRAND · NOT APPROVED</text>'),
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
        "Owner must decide rights/license before public use. See metadata/rights-and-sources.json.\n\n"
        "Run python3 scripts/generate-brand-kit.py --raster --check with the same toolchain for drift verification. "
        "Delete only a known generated kit directory to rebuild after a source change; do not change manifest hashes by hand.\n").encode()
    files["review/index.html"] = b'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Proposed Decky Stream kit</title><link rel="stylesheet" href="review.css"></head><body><main><h1>Decky Stream: proposed brand</h1><p>Human creative and rights review pending. Live product icon and theme are unchanged.</p><img class="wordmark" src="../docs/wordmark.svg" alt="Proposed Decky Stream wordmark"><h2>Actual-size geometry</h2><img class="sheet" src="legibility-sheet.svg" alt="Proposed play-and-transmission mark at 16, 24, 32, 64 and 128 pixels"><h2>Repository preview</h2><img class="social" src="../github/social-preview.svg" alt="Proposed Decky Stream social preview, explicitly marked not approved"><p>Check the README, rights inventory, contrast report and manifest before review. SVG text uses DejaVu Sans. No animation or remote assets.</p></main></body></html>\n'
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
    parser.add_argument("--output", type=Path, default=ROOT / "dist/branding-draft")
    parser.add_argument("--raster", action="store_true", help="Include PNG exports using exact locked tools")
    parser.add_argument("--check", action="store_true", help="Read-only exact output drift verification")
    args = parser.parse_args()
    try:
        output = args.output.absolute()
        if output.resolve().is_relative_to(ROOT) and not output.resolve().is_relative_to(ROOT / "dist"):
            raise ValueError("Generated kit must be in dist/ or outside the repository")
        files = render(raster=args.raster)
        write_or_check(files, output, check=args.check)
    except (ValueError, OSError, ET.ParseError, subprocess.SubprocessError) as error:
        parser.error(str(error))
    print(json.dumps({"status": "verified" if args.check else "prepared", "approval": "proposed-unapproved",
                      "output": str(output), "files": len(files), "archive_sha256": digest(files["decky-stream-proposed.zip"])}))


if __name__ == "__main__":
    main()
