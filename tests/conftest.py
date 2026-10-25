"""Shared helpers for the mintlify-convert test suite."""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def run_cli(monkeypatch, capsys):
    """Run the CLI in-process; returns (exit_code, stdout, stderr)."""
    from mintlify_convert.cli import main

    def _run(*args):
        monkeypatch.setattr(sys, "argv", ["mintlify-convert", *map(str, args)])
        code = 0
        try:
            main()
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        out = capsys.readouterr()
        return code, out.out, out.err

    return _run


def run_python(code: str, timeout: float = 30):
    """Run a snippet in a fresh interpreter with a hard time limit.

    Used for regex time-bound tests so a catastrophic-backtracking regression
    fails the test instead of hanging CI. Raises pytest failure on timeout.
    """
    try:
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"conversion exceeded {timeout}s hard limit (regex blow-up?)")
