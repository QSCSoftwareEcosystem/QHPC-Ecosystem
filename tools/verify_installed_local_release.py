#!/usr/bin/env python3
"""Verify an installed EQO Local wheel outside the source checkout."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from urllib.request import urlopen


def _run(command: list[str], *, cwd: Path, environment: dict[str, str]) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no output"
        raise RuntimeError(
            f"installed release command failed ({command[-1]}): {detail}"
        )
    return result.stdout


def _python(environment_root: Path) -> Path:
    directory = "Scripts" if os.name == "nt" else "bin"
    name = "python.exe" if os.name == "nt" else "python"
    return environment_root / directory / name


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def verify(wheel: Path) -> None:
    wheel = wheel.expanduser().resolve()
    if not wheel.is_file():
        raise FileNotFoundError(f"EQO Local wheel not found: {wheel}")
    with tempfile.TemporaryDirectory(prefix="eqo-installed-") as temporary_name:
        temporary = Path(temporary_name)
        environment_root = temporary / "venv"
        home = temporary / "home"
        work = temporary / "work"
        work.mkdir()
        venv.EnvBuilder(with_pip=True).create(environment_root)
        python = _python(environment_root)
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        _run(
            [str(python), "-m", "pip", "install", f"{wheel}[local]"],
            cwd=work,
            environment=environment,
        )
        base = [str(python), "-m", "qhpc_ecosystem.cli", "local"]
        ports: list[str] = []
        while len(ports) < 3:
            candidate = str(_free_port())
            if candidate not in ports:
                ports.append(candidate)
        up = [
            *base,
            "up",
            "--home",
            str(home),
            "--port",
            ports[0],
            "--api-port",
            ports[1],
            "--assistant-port",
            ports[2],
            "--timeout",
            "30",
        ]
        down = [*base, "down", "--home", str(home)]
        try:
            for attempt in range(2):
                lifecycle_environment = environment
                if attempt == 1:
                    lifecycle_environment = {
                        **environment,
                        "HTTP_PROXY": "http://127.0.0.1:9",
                        "HTTPS_PROXY": "http://127.0.0.1:9",
                        "NO_PROXY": "127.0.0.1,localhost",
                    }
                _run(up, cwd=work, environment=lifecycle_environment)
                status = json.loads(
                    _run(
                        [*base, "status", "--home", str(home), "--json"],
                        cwd=work,
                        environment=lifecycle_environment,
                    )
                )
                if status.get("status") != "ready":
                    raise RuntimeError("installed EQO Local stack is not ready")
                with urlopen(
                    f"http://127.0.0.1:{ports[2]}/v1/health", timeout=5
                ) as response:
                    assistant = json.load(response)
                if assistant.get("pages") != 60:
                    raise RuntimeError("installed Assistant corpus is incomplete")
                if any((home / "data" / "services").iterdir()):
                    raise RuntimeError("installed EQO Local created a source checkout")
                _run(down, cwd=work, environment=lifecycle_environment)
        finally:
            subprocess.run(
                down,
                cwd=work,
                env=environment,
                check=False,
                capture_output=True,
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    verify(args.wheel)
    print("Installed EQO Local lifecycle verified: start, health, stop, restart")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
