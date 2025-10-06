from __future__ import annotations
import sys
from pymd.app import run_app


def main() -> int:
    """Module entrypoint for `python -m pymd.main` or `python -m pymd` (via __main__)."""
    return run_app(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
