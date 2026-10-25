"""CLI behavior: flags, exit codes, config generation."""

import json

import pytest


@pytest.fixture
def docs(tmp_path):
    d = tmp_path / "docs"
    (d / "guides").mkdir(parents=True)
    (d / "intro.mdx").write_text("# Intro\n\nWelcome.\n")
    (d / "guides" / "setup.mdx").write_text("# Setup\n\nSet it up.\n")
    return d


def test_missing_input_exits_1(tmp_path, run_cli):
    code, out, err = run_cli(tmp_path / "nope.mdx")
    assert code == 1
    assert "does not exist" in err


def test_directory_requires_output(docs, run_cli):
    code, out, err = run_cli(docs)
    assert code == 1
    assert "Output directory required" in err


def test_output_dir_created(tmp_path, run_cli):
    f = tmp_path / "a.mdx"
    f.write_text("# A\n\nBody.\n")
    code, _, _ = run_cli(f, "-o", tmp_path / "new" / "sub" / "o.mdx")
    assert code == 0
    assert (tmp_path / "new" / "sub" / "o.mdx").exists()


def test_no_config_by_default(docs, tmp_path, run_cli):
    out = tmp_path / "out"
    code, _, _ = run_cli(docs, "-o", out)
    assert code == 0
    assert not (out / "docs.json").exists() and not (out / "mint.json").exists()


def test_generate_config_writes_docs_json(docs, tmp_path, run_cli):
    out = tmp_path / "out"
    code, _, _ = run_cli(docs, "-o", out, "--generate-config", "--project-name", "Proj")
    assert code == 0
    assert (out / "docs.json").is_file()
    assert not (out / "mint.json").exists()
    assert json.loads((out / "docs.json").read_text())["name"] == "Proj"


def test_legacy_flag_writes_mint_json(docs, tmp_path, run_cli):
    out = tmp_path / "out"
    code, _, _ = run_cli(docs, "-o", out, "--generate-config", "--legacy-mint-json")
    assert code == 0
    assert (out / "mint.json").is_file()
    assert not (out / "docs.json").exists()


def test_deprecated_alias_writes_mint_json_and_warns(docs, tmp_path, run_cli):
    out = tmp_path / "out"
    code, so, se = run_cli(docs, "-o", out, "--generate-mint-json")
    assert code == 0
    assert (out / "mint.json").is_file()
    assert not (out / "docs.json").exists()
    assert "deprecated" in (so + se).lower()


def test_use_ai_description_flag_removed(docs, tmp_path, run_cli):
    code, so, se = run_cli(docs, "-o", tmp_path / "out", "--use-ai-description")
    assert code == 2
    assert "unrecognized" in se.lower()


def test_help_does_not_mention_removed_features(run_cli):
    code, so, se = run_cli("--help")
    text = (so + se).lower()
    assert code == 0
    assert "use-ai-description" not in text and "openai" not in text
    for flag in ("--generate-config", "--legacy-mint-json", "--generate-mint-json"):
        assert flag in text


def test_validate_flag_reports_real_problem_only(tmp_path, run_cli):
    f = tmp_path / "a.mdx"
    f.write_text("# A\n\nBody.\n\n```\n<Note>in code\n```\n")
    code, so, se = run_cli(f, "-o", tmp_path / "o.mdx", "--validate")
    assert code == 0
    assert "unclosed" not in (so + se).lower()


def test_download_assets_flag_copies_images(tmp_path, run_cli):
    d = tmp_path / "docs"
    d.mkdir()
    (d / "p.mdx").write_text("# P\n\nIntro.\n\n![x](pic.png)\n")
    (d / "pic.png").write_bytes(b"PNG")
    out = tmp_path / "out"
    code, _, _ = run_cli(d, "-o", out, "--download-assets")
    assert code == 0
    assert (out / "images" / "pic.png").is_file()


def test_idempotent_through_cli(tmp_path, run_cli):
    src = tmp_path / "a.mdx"
    src.write_text("# T\n\nIntro.\n\n1. **One** - first\n2. Two\n\n> **Note:** hi\n")
    first, second = tmp_path / "1.mdx", tmp_path / "2.mdx"
    assert run_cli(src, "-o", first)[0] == 0
    assert run_cli(first, "-o", second)[0] == 0
    assert first.read_text() == second.read_text()
