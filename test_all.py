#!/usr/bin/env python3
"""
AstraNote Comprehensive Test Script

This script runs all tests for AstraNote, including unit tests and CLI integration tests.
It provides detailed notes for each test case and cleans up data afterward.
"""

import os
import sys
import shutil
from pathlib import Path

project_dir = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_dir))

def get_active_environment():
    env = os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_PREFIX")
    if env:
        return env
    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        return sys.prefix
    return None


def get_virtualenv_python():
    for venv_name in (".venv", "venv"):
        candidate = project_dir / venv_name / "Scripts" / "python.exe"
        if candidate.exists():
            return str(candidate)
    return None


def ensure_virtualenv_active():
    if get_active_environment():
        return
    if os.environ.get("ASTRANOTE_TEST_ACTIVATED") == "1":
        return
    venv_python = get_virtualenv_python()
    if not venv_python:
        print("No active Python environment found.")
        print("Please activate a virtual environment or create one in '.venv' or 'venv'.")
        sys.exit(1)
    print(f"Re-launching test script using virtual environment: {venv_python}")
    env = os.environ.copy()
    env["ASTRANOTE_TEST_ACTIVATED"] = "1"
    import subprocess
    result = subprocess.run([venv_python, str(project_dir / "test_all.py")], env=env)
    sys.exit(result.returncode)

ensure_virtualenv_active()


def print_test_header(test_name, description):
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"DESCRIPTION: {description}")
    print('='*60)


def print_test_result(success, output, error=""):
    if success:
        print("✅ PASSED")
    else:
        print("❌ FAILED")
    if output:
        print("OUTPUT:")
        print(output)
    if error:
        print("ERROR:")
        print(error)


def run_bdd_tests():
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/steps/test_steps.py", "-v"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def main():
    data_dir = project_dir / "data"

    if data_dir.exists():
        shutil.rmtree(data_dir)
        print("Cleaned up existing data directory")

    active_env = get_active_environment()
    if not active_env:
        print("Please activate your Python environment before running this test script.")
        return 1

    print("Starting AstraNote Comprehensive Tests")
    print(f"Project directory: {project_dir}")
    print(f"Data directory: {data_dir}")
    print(f"Active environment: {active_env}")

    all_passed = True

    # ---- Unit tests (core modules) ----
    print_test_header(
        "Unit Tests",
        "Run pytest to execute unit tests covering core Note, NoteStore, and encryption"
    )
    import subprocess
    unit_result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_core.py", "-q"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    success = unit_result.returncode == 0
    print_test_result(success, unit_result.stdout, unit_result.stderr)
    if not success:
        all_passed = False

    # ---- BDD tests (all CLI behaviour) ----
    print_test_header(
        "BDD Tests",
        "Run Behavior-Driven Development tests covering all CLI CRUD scenarios"
    )
    code, out, err = run_bdd_tests()
    success = code == 0
    print_test_result(success, out, err)
    if not success:
        all_passed = False
    if data_dir.exists():
        shutil.rmtree(data_dir)
        print("✅ Data directory removed")
    else:
        print("⚠️  No data directory to clean")

    print(f"\n{'='*60}")
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("AstraNote is working correctly.")
    else:
        print("❌ SOME TESTS FAILED! Please check output above.")
    print('='*60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
