#!/usr/bin/env python3
"""Build a verified EQO Local wheel from clean frontend dependencies."""

from __future__ import annotations

import argparse
import hashlib
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


def _require_reproducible_frontend() -> None:
    missing = [str(path.relative_to(ROOT)) for path in GENERATED_ASSETS if not path.is_file()]
    if missing:
        raise ReleaseBuildError(
            "frontend build did not produce: " + ", ".join(missing)
        )
    result = subprocess.run(
        [
            "git",
            "diff",
            "--quiet",
            "--",
            *(str(path.relative_to(ROOT)) for path in GENERATED_ASSETS),
        ],
        cwd=ROOT,
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise ReleaseBuildError("cannot verify generated frontend assets with git")
    if result.returncode == 1:
        raise ReleaseBuildError(
            "the clean frontend build changed committed assets; review and commit "
            "the generated Workbench before producing a release artifact"
        )


def build_local_release(output_dir: Path) -> tuple[Path, Path]:
    npm = shutil.which("npm")
    if npm is None:
        raise ReleaseBuildError("npm is required to build the EQO Workbench")

    _run((npm, "ci", "--prefix", str(FRONTEND)))
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
        checksum_file = resolved_output / "SHA256SUMS"
        temporary_checksum = temporary / "SHA256SUMS"
        temporary_checksum.write_text(
            f"{_sha256(target)}  {target.name}\n",
            encoding="utf-8",
        )
        os.replace(temporary_checksum, checksum_file)
    return target, checksum_file


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
        wheel, checksums = build_local_release(args.output_dir)
    except ReleaseBuildError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"EQO Local wheel: {wheel}")
    print(f"Checksums: {checksums}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
