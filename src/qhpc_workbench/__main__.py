"""Run the separately deployable Django Workbench."""

from __future__ import annotations

import argparse
import os


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Serve the QHPC Django Workbench")
    value.add_argument("--host", default="127.0.0.1")
    value.add_argument("--port", type=int, default=8080)
    value.add_argument("--api-base", default="http://127.0.0.1:8081")
    return value


def main() -> int:
    args = parser().parse_args()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "qhpc_workbench.settings")
    os.environ["QHPC_API_BASE"] = args.api_base.rstrip("/")
    os.environ["QHPC_WORKBENCH_HOST"] = args.host

    from django.core.management import execute_from_command_line

    execute_from_command_line(
        [
            "qhpc-workbench",
            "runserver",
            f"{args.host}:{args.port}",
            "--noreload",
        ]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
