from __future__ import annotations

import hashlib
from pathlib import Path

from tools import build_local_release


def test_release_builder_runs_clean_frontend_and_python_gates(
    tmp_path: Path, monkeypatch
) -> None:
    commands: list[tuple[str, ...]] = []

    def run(command) -> None:
        values = tuple(command)
        commands.append(values)
        if "wheel" in values:
            wheel_root = Path(values[values.index("--wheel-dir") + 1])
            (wheel_root / "qhpc_ecosystem-0.1.0-py3-none-any.whl").write_bytes(
                b"verified wheel"
            )

    monkeypatch.setattr(
        build_local_release.shutil,
        "which",
        lambda _name: "/usr/bin/npm",
    )
    monkeypatch.setattr(build_local_release, "_run", run)
    monkeypatch.setattr(
        build_local_release,
        "_require_reproducible_frontend",
        lambda: None,
    )

    wheel, checksums = build_local_release.build_local_release(tmp_path / "dist")

    assert [command[1:3] for command in commands[:4]] == [
        ("ci", "--prefix"),
        ("run", "check"),
        ("test", "--prefix"),
        ("run", "build"),
    ]
    assert commands[4][-2:] == ("pytest", "-q")
    assert "wheel" in commands[5]
    assert wheel.read_bytes() == b"verified wheel"
    assert checksums.read_text(encoding="utf-8") == (
        hashlib.sha256(b"verified wheel").hexdigest()
        + "  qhpc_ecosystem-0.1.0-py3-none-any.whl\n"
    )


def test_release_builder_detects_stale_generated_frontend(
    tmp_path: Path, monkeypatch
) -> None:
    generated = tmp_path / "composer.js"
    generated.write_text("generated", encoding="utf-8")

    class Result:
        returncode = 1

    monkeypatch.setattr(build_local_release, "ROOT", tmp_path)
    monkeypatch.setattr(build_local_release, "GENERATED_ASSETS", (generated,))
    monkeypatch.setattr(
        build_local_release.subprocess,
        "run",
        lambda *_args, **_kwargs: Result(),
    )

    try:
        build_local_release._require_reproducible_frontend()
    except build_local_release.ReleaseBuildError as error:
        assert "changed committed assets" in str(error)
    else:
        raise AssertionError("stale generated frontend was accepted")
