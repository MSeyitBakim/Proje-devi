"""Environment check: `python scripts/doctor.py` (run from the backend/ folder).

Prints the Python version, which dependencies import (with versions), packages whose names
look like typos of our dependencies (e.g. 'httpxz'), and the full traceback if the API or
worker module fails to import. Paste the output when asking for help.
"""

import importlib
import importlib.metadata as metadata
import sys
import traceback
from difflib import get_close_matches
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REQUIRED = {"fastapi": "fastapi", "uvicorn": "uvicorn", "httpx": "httpx",
            "bs4": "beautifulsoup4", "pydantic": "pydantic", "starlette": "starlette"}


def main() -> int:
    problems = 0
    print(f"python      {sys.version.split()[0]}  ({sys.executable})")
    if sys.version_info < (3, 12):
        print("  !! Python 3.12+ is required"); problems += 1
    for module, dist in REQUIRED.items():
        try:
            importlib.import_module(module)
            print(f"ok          {dist} {metadata.version(dist)}")
        except Exception as exc:  # noqa: BLE001
            print(f"MISSING     {dist}: {type(exc).__name__}: {exc}"); problems += 1

    installed = {d.metadata["Name"].lower() for d in metadata.distributions() if d.metadata["Name"]}
    for name in sorted(installed):
        if name not in REQUIRED.values() and get_close_matches(name, list(REQUIRED.values()), 1, 0.85):
            print(f"SUSPICIOUS  '{name}' looks like a typo of a required package. "
                  f"Uninstall it (pip uninstall {name}) and install the real one.")
            problems += 1

    for target in ("app.main", "app.worker"):
        try:
            importlib.import_module(target)
            print(f"ok          import {target}")
        except Exception:  # noqa: BLE001
            print(f"FAILED      import {target}"); traceback.print_exc(); problems += 1
    print("\nNo problems found." if not problems else f"\n{problems} problem(s) found.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
