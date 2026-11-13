#!/usr/bin/env python3
"""Run only the hash-pinned, separately obtained Identity source validator.

This command performs no download or installation. Redirect stdout to retain a
portable content-bound proof. A successful source check is not artwork approval.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validator", required=True, type=Path)
    args = parser.parse_args()
    lock = json.loads((ROOT / ".identity/toolchain.lock.json").read_text())
    pin = lock["files"]["scripts/validate_identity.py"]
    actual = hashlib.sha256(args.validator.read_bytes()).hexdigest()
    if actual != pin["sha256"]:
        parser.error("Identity validator differs from the reviewed immutable pin")
    process = subprocess.run([sys.executable, str(args.validator.absolute()), "--repository-root", ".",
                              "--format", "json", "--snapshot"], cwd=ROOT, text=True, capture_output=True)
    if process.returncode not in (0, 1) or not process.stdout.strip():
        parser.error("Pinned validator did not return its diagnostic contract")
    result = json.loads(process.stdout)
    proof = {"schema": "decky-stream.identity-source-proof/v1", "identity_revision": lock["revision"],
             "validator": pin, "python": platform.python_version(), "platform": platform.platform(),
             "command": "python3 VERIFIED_IDENTITY_VALIDATOR --repository-root . --format json --snapshot",
             "exit_code": process.returncode, "source_result": result,
             "limits": "Source contract only. Candidate art is unapproved; no Identity generation, device, release or publication qualification."}
    print(json.dumps(proof, sort_keys=True, indent=2))
    return 0 if process.returncode == 0 and result.get("valid") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
