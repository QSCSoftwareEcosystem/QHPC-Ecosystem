#!/usr/bin/env python3
"""Build a verified EQO Local wheel from clean frontend dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "workbench" / "frontend"
GENERATED_ASSETS = (
    ROOT / "src" / "qhpc_workbench" / "static" / "qhpc_workbench" / "composer.js",
    ROOT / "src" / "qhpc_workbench" / "static" / "qhpc_workbench" / "composer.css",
)
SOFTWARE_INVENTORY = ROOT / "release" / "eqo-local-software-inventory.json"


class ReleaseBuildError(RuntimeError):
    """Raised when a release artifact cannot be reproduced safely."""


def _run(command: Sequence[str]) -> None:
    print("+ " + " ".join(command), flush=True)
    try:
        subprocess.run(command, cwd=ROOT, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise ReleaseBuildError(f"release build command failed: {command[0]}") from error


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _git_blob_digest(path: Path) -> str:
    content = path.read_bytes()
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def _require_reproducible_frontend() -> None:
    missing = [str(path.relative_to(ROOT)) for path in GENERATED_ASSETS if not path.is_file()]
    if missing:
        raise ReleaseBuildError(
            "frontend build did not produce: " + ", ".join(missing)
        )
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--stage",
            "--",
            *(str(path.relative_to(ROOT)) for path in GENERATED_ASSETS),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ReleaseBuildError(
            "cannot verify generated frontend assets with the Git index"
        )
    indexed: dict[str, str] = {}
    for line in result.stdout.splitlines():
        metadata, separator, name = line.partition("\t")
        fields = metadata.split()
        if separator and len(fields) >= 2:
            indexed[name] = fields[1]
    changed = [
        str(path.relative_to(ROOT))
        for path in GENERATED_ASSETS
        if indexed.get(str(path.relative_to(ROOT))) != _git_blob_digest(path)
    ]
    if changed:
        raise ReleaseBuildError(
            "the clean frontend build changed committed assets; review and commit "
            "the generated Workbench before producing a release artifact: "
            + ", ".join(changed)
        )


def build_local_release(output_dir: Path) -> tuple[Path, Path, Path]:
    npm = shutil.which("npm")
    if npm is None:
        raise ReleaseBuildError("npm is required to build the EQO Workbench")

    # Vulnerability scanning is a separate release gate.  Suppress npm's
    # implicit audit request here so a package-registry advisory outage cannot
    # stall an otherwise reproducible install and build.
    _run((npm, "ci", "--no-audit", "--prefix", str(FRONTEND)))
    _run((npm, "run", "check", "--prefix", str(FRONTEND)))
    _run((npm, "test", "--prefix", str(FRONTEND)))
    _run((npm, "run", "build", "--prefix", str(FRONTEND)))
    _require_reproducible_frontend()
    _run((sys.executable, "-m", "pytest", "-q"))

    resolved_output = output_dir.expanduser().resolve()
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".eqo-local-release-",
        dir=resolved_output.parent,
    ) as temporary_name:
        temporary = Path(temporary_name)
        wheel_root = temporary / "wheel"
        wheel_root.mkdir()
        _run(
            (
                sys.executable,
                "-m",
                "pip",
                "wheel",
                ".",
                "--no-deps",
                "--no-build-isolation",
                "--wheel-dir",
                str(wheel_root),
            )
        )
        wheels = list(wheel_root.glob("qhpc_ecosystem-*.whl"))
        if len(wheels) != 1:
            raise ReleaseBuildError(
                f"expected one EQO Local wheel, found {len(wheels)}"
            )
        resolved_output.mkdir(parents=True, exist_ok=True)
        target = resolved_output / wheels[0].name
        os.replace(wheels[0], target)
        try:
            inventory_document = json.loads(
                SOFTWARE_INVENTORY.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            raise ReleaseBuildError(
                f"cannot read EQO Local software inventory: {error}"
            ) from error
        if inventory_document.get("release", {}).get("version") != "0.1.0":
            raise ReleaseBuildError("EQO Local software inventory version differs")
        if inventory_document.get("release", {}).get("review_status") not in {
            "approved",
            "project-review-required",
        }:
            raise ReleaseBuildError("EQO Local software inventory review status is invalid")
        for section in (
            "included_software",
            "required_dependencies",
            "optional_scientific_runtimes",
        ):
            entries = inventory_document.get(section)
            if not isinstance(entries, list) or not entries:
                raise ReleaseBuildError(
                    f"EQO Local software inventory section is empty: {section}"
                )
            if any(not item.get("name") or not item.get("license") for item in entries):
                raise ReleaseBuildError(
                    f"EQO Local software inventory lacks a name or license: {section}"
                )
        inventory = resolved_output / "EQO_LOCAL_SOFTWARE_INVENTORY.json"
        shutil.copyfile(SOFTWARE_INVENTORY, inventory)
        checksum_file = resolved_output / "SHA256SUMS"
        temporary_checksum = temporary / "SHA256SUMS"
        temporary_checksum.write_text(
            f"{_sha256(target)}  {target.name}\n"
            f"{_sha256(inventory)}  {inventory.name}\n",
            encoding="utf-8",
        )
        os.replace(temporary_checksum, checksum_file)
    return target, checksum_file, inventory


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Clean, type-check, test, and build the Workbench; run the Python "
            "suite; then produce a checksummed EQO Local wheel."
        )
    )
    parser.add_argument(
        "--output-dir",
        default="dist",
        type=Path,
        help="release artifact directory (default: dist)",
    )
    args = parser.parse_args(argv)
    try:
        wheel, checksums, inventory = build_local_release(args.output_dir)
    except ReleaseBuildError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"EQO Local wheel: {wheel}")
    print(f"Checksums: {checksums}")
    print(f"Software inventory: {inventory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
