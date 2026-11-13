#!/usr/bin/env python3
"""Build the small MIT capture plugin against Debian bookworm's stable ABIs.

The image pins the base digest; a build receipt records its actual image ID,
compiler and installed package versions. The final compile runs without network
and its paths/build ID do not encode the host or staging directory. Repeating
with the same source, image and tools must produce identical bytes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "steamdeck/capture"
DOCKERFILE = SOURCE / "build.Dockerfile"
DOCKER_ENV = {key: value for key, value in os.environ.items() if key not in {
    "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"}}


def output(*args):
    return subprocess.check_output(args, text=True, env=DOCKER_ENV).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO / "dist/libgstobsgodcapture.so")
    parser.add_argument("--receipt", type=Path, default=REPO / "dist/capture-build.json")
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.receipt = args.receipt.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    # This builder only operates on this executor's managed local daemon. Keep
    # its registry/proxy configuration and credentials unchanged.
    docker = ["docker", "--host=unix:///var/run/docker.sock"]
    dockerfile_hash = hashlib.sha256(DOCKERFILE.read_bytes()).hexdigest()
    image = "obsgod-capture-builder:" + dockerfile_hash[:16]
    certificate = Path(os.environ.get("CODEX_PROXY_CERT", "/etc/ssl/certs/ca-certificates.crt"))
    if not certificate.is_file():
        raise SystemExit("A trusted system/proxy CA bundle is required for the capture builder")
    # Forward only already configured proxy inputs. This also supports act's
    # Engine client, which does not inherit the outer Docker client's presets.
    proxy_args = [argument for key in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy") if key in DOCKER_ENV for argument in ("--build-arg", key)]
    subprocess.run(docker + ["build", *proxy_args, "--platform", "linux/amd64", "--secret", "id=proxy_ca,src=" + str(certificate), "-f", str(DOCKERFILE), "-t", image, str(SOURCE)], check=True, env=DOCKER_ENV)
    image_id = output(*(docker + ["image", "inspect", image, "--format", "{{.Id}}"] ))
    with tempfile.TemporaryDirectory(prefix="obsgod-capture-") as temporary:
        work = Path(temporary)
        command = """set -eu
export LC_ALL=C TZ=UTC SOURCE_DATE_EPOCH=0
cd /out
cc -D_GNU_SOURCE -std=c11 -fPIC -shared -O2 -Wall -Wextra -Werror \\
  -ffile-prefix-map=/src=. -fmacro-prefix-map=/src=. -Wl,--build-id=none \\
  -o libgstobsgodcapture.so /src/gstobsgodcapture.c \\
  $(pkg-config --cflags --libs gstreamer-1.0 gstreamer-base-1.0 gstreamer-video-1.0 libpipewire-0.3)
cc --version > compiler.txt
dpkg-query -W -f='${binary:Package}=${Version}\\n' > packages.txt
readelf --version-info libgstobsgodcapture.so > symbol-versions.txt
readelf -d libgstobsgodcapture.so > dynamic.txt
"""
        subprocess.run(docker + ["run", "--rm", "--network", "none", "--platform", "linux/amd64", "--user", str(os.getuid()) + ":" + str(os.getgid()), "--mount", "type=bind,src=" + str(SOURCE) + ",dst=/src,readonly", "--mount", "type=bind,src=" + str(work) + ",dst=/out", image, "sh", "-ec", command], check=True, env=DOCKER_ENV)
        data = (work / "libgstobsgodcapture.so").read_bytes()
        if (data[:6] != b"\x7fELF\x02\x01" or int.from_bytes(data[16:18], "little") != 3
                or int.from_bytes(data[18:20], "little") != 62):
            raise SystemExit("Capture builder did not produce a Linux amd64 shared library")
        args.output.write_bytes(data)
        args.output.chmod(0o600)
        receipt = {"library": args.output.name, "sha256": hashlib.sha256(data).hexdigest(), "platform": "linux/amd64", "image": image, "image_id": image_id, "dockerfile_sha256": dockerfile_hash, "source_sha256": hashlib.sha256((SOURCE / "gstobsgodcapture.c").read_bytes()).hexdigest(), "compiler": (work / "compiler.txt").read_text(), "packages": (work / "packages.txt").read_text().splitlines(), "symbol_versions": (work / "symbol-versions.txt").read_text(), "dynamic": (work / "dynamic.txt").read_text(), "network_during_compile": False}
        args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"library": str(args.output), "sha256": receipt["sha256"], "builder_image": image_id, "receipt": str(args.receipt)}))


if __name__ == "__main__":
    main()
