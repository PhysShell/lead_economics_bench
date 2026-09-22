"""Console entry point: ``leadbench <command>``.

A thin wrapper over the scripts so the package is usable after
``pip install -e .`` without remembering paths.

    leadbench run --suite smoke
    leadbench report
    leadbench download --all
    leadbench regimes
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"

_COMMANDS = {
    "run": "run_benchmark.py",
    "report": "build_report.py",
    "download": "download_datasets.py",
}


def _list_regimes() -> int:
    from .synthetic.config import REGIMES
    from .synthetic.mmm_dgp import MMM_REGIMES

    print("lead-track regimes:")
    for name in sorted(REGIMES):
        overrides = ", ".join(f"{k}={v}" for k, v in list(REGIMES[name].items())[:3])
        print(f"  {name:34s} {overrides}")
    print("\nMMM regimes:")
    for name in sorted(MMM_REGIMES):
        print(f"  {name:34s} {MMM_REGIMES[name]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        print("commands: " + ", ".join(list(_COMMANDS) + ["regimes"]))
        return 0

    cmd, rest = argv[0], argv[1:]
    if cmd == "regimes":
        return _list_regimes()
    if cmd not in _COMMANDS:
        print(f"unknown command {cmd!r}; try --help", file=sys.stderr)
        return 2

    script = _SCRIPTS / _COMMANDS[cmd]
    if not script.exists():
        print(f"script not found: {script}", file=sys.stderr)
        return 2
    sys.argv = [str(script), *rest]
    runpy.run_path(str(script), run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
