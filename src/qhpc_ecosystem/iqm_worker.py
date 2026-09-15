"""Dedicated ``qhpc-iqm-worker`` console entry point.

This wrapper keeps the command named in the FTQC operation contract while
reusing EQO's shared CLI implementation. ``--catalog`` remains a global option
and is therefore inserted before the worker subcommand when supplied.
"""

from __future__ import annotations

import sys
from typing import Sequence

from .cli import main as cli_main


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    position = 0
    if len(arguments) >= 2 and arguments[0] == "--catalog":
        position = 2
    return cli_main(arguments[:position] + ["iqm-worker"] + arguments[position:])


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
