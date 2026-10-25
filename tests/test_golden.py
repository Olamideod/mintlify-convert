"""Golden-file tests: converter output must match the committed fixtures and examples."""

from pathlib import Path

import pytest

from mintlify_convert.converter import MintlifyConverter

from .conftest import FIXTURES, REPO_ROOT


def _convert(path: Path) -> str:
    return MintlifyConverter().convert(path.read_text(encoding="utf-8"), source_file=path)


def test_sample_matches_expected_output():
    assert _convert(FIXTURES / "sample.mdx") == (FIXTURES / "expected_output.mdx").read_text(
        encoding="utf-8"
    )


def test_expected_output_is_a_fixed_point():
    expected = (FIXTURES / "expected_output.mdx").read_text(encoding="utf-8")
    assert MintlifyConverter().convert(expected) == expected


@pytest.mark.parametrize("name", ["basic", "advanced"])
def test_examples_match_converter(name):
    example = REPO_ROOT / "examples" / name
    if not (example / "input.mdx").exists():
        pytest.skip(f"example {name} not present (installed package?)")
    assert _convert(example / "input.mdx") == (example / "output.mdx").read_text(encoding="utf-8")
