"""test_all.py — comprehensive test runner for AstraNotes.

Runs the full suite (unit + BDD) and reports a summary.
Stress tests are excluded by default; use --stress to include them.

Usage:
    python test_all.py            # unit + BDD (fast)
    python test_all.py --stress   # include stress tests
"""
from __future__ import annotations

import subprocess
import sys


def main() -> None:
    include_stress = "--stress" in sys.argv[1:]

    base_args = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
    ]

    if not include_stress:
        base_args += ["-m", "not stress"]

    print("=" * 60)
    print("AstraNotes test suite")
    if include_stress:
        print("Mode: unit + BDD + stress")
    else:
        print("Mode: unit + BDD  (use --stress to include stress tests)")
    print("=" * 60)

    result = subprocess.run(base_args)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
