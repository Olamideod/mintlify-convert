"""docs.json (default) and legacy mint.json generation."""

import json
from pathlib import Path

import jsonschema  # hard requirement: schema tests must fail loudly if missing
import pytest

from mintlify_convert.navigation import generate_docs_json, generate_enhanced_mint_json

SCHEMA_PATH = Path(__file__).parent / "fixtures" / "docs-schema.json"

META = {
    "api/auth": {"title": "Authentication", "path": "api/auth", "group": "api"},
    "guides/best": {"title": "Best Practices", "path": "guides/best", "group": "guides"},
    "getting-started/intro": {
        "title": "Intro",
        "path": "getting-started/intro",
        "group": "getting-started",
    },
    "getting-started/install": {
        "title": "Install",
        "path": "getting-started/install",
        "group": "getting-started",
    },
}


def build(tmp_path, meta=META, **kw):
    out = tmp_path / "docs.json"
    generate_docs_json(meta, out, **kw)
    return json.loads(out.read_text(encoding="utf-8"))


def walk(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k, v
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)


def groups_of(cfg):
    nav = cfg["navigation"]
    return nav["groups"] if isinstance(nav, dict) else nav


def test_structure_always_checked(tmp_path):
    cfg = build(tmp_path, project_name="Proj", primary_color="#112233")
    assert cfg["theme"] == "mint"
    assert cfg["name"] == "Proj"
    assert cfg["colors"]["primary"] == "#112233"
    assert "$schema" in cfg and cfg["$schema"].startswith("https://")
    groups = groups_of(cfg)
    assert groups and all("group" in g and isinstance(g["pages"], list) for g in groups)


def test_valid_against_official_schema(tmp_path):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    cfg = build(
        tmp_path,
        project_name="Proj",
        primary_color="#0D9373",
        light_color="#07C983",
        dark_color="#0D9373",
        github="https://github.com/o/r",
    )
    jsonschema.validate(cfg, schema)


def test_minimal_config_valid_against_schema(tmp_path):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(build(tmp_path), schema)


def test_getting_started_first_then_alphabetical(tmp_path):
    names = [g["group"] for g in groups_of(build(tmp_path))]
    assert names == ["Getting Started", "Api", "Guides"]


def test_sort_pages_honored(tmp_path):
    cfg = build(tmp_path, sort_pages=True)
    gs = next(g for g in groups_of(cfg) if g["group"] == "Getting Started")
    assert gs["pages"] == ["getting-started/install", "getting-started/intro"]


def test_no_null_values_anywhere(tmp_path):
    cfg = build(tmp_path)
    assert [k for k, v in walk(cfg) if v is None] == []


def test_unset_options_are_omitted_without_placeholders(tmp_path):
    text = json.dumps(build(tmp_path))
    for placeholder in ("example.com", "twitter.com/example", "yourusername", "your.email"):
        assert placeholder not in text
    for key in ("twitter", "linkedin", "github"):
        assert f'"{key}"' not in text


def test_provided_social_and_support_urls_appear(tmp_path):
    text = json.dumps(
        build(tmp_path, github="https://github.com/o/r", support_url="https://s.test")
    )
    assert "https://github.com/o/r" in text
    assert "https://s.test" in text


def test_every_page_present_exactly_once(tmp_path):
    cfg = build(tmp_path)
    pages = [p for g in groups_of(cfg) for p in g["pages"]]
    assert sorted(pages) == sorted(META)


def test_empty_metadata_does_not_crash(tmp_path):
    out = tmp_path / "docs.json"
    generate_docs_json({}, out)
    assert out.exists()
    json.loads(out.read_text())


# --- legacy mint.json ------------------------------------------------------


def test_legacy_mint_json_getting_started_first(tmp_path):
    out = tmp_path / "mint.json"
    generate_enhanced_mint_json(META, out)
    cfg = json.loads(out.read_text())
    assert [g["group"] for g in cfg["navigation"]] == ["Getting Started", "Api", "Guides"]


def test_legacy_mint_json_has_no_null_values(tmp_path):
    out = tmp_path / "mint.json"
    generate_enhanced_mint_json(META, out)
    assert [k for k, v in walk(json.loads(out.read_text())) if v is None] == []


# --- wave 2: navigation details --------------------------------------------


def test_getting_started_then_documentation_then_alphabetical(tmp_path):
    meta = {
        "zeta/a": {"title": "Z", "path": "zeta/a", "group": "zeta"},
        "intro": {"title": "I", "path": "intro", "group": "Documentation"},
        "alpha/a": {"title": "A", "path": "alpha/a", "group": "alpha"},
        "getting-started/x": {
            "title": "X",
            "path": "getting-started/x",
            "group": "getting-started",
        },
    }
    names = [g["group"] for g in groups_of(build(tmp_path, meta))]
    assert names == ["Getting Started", "Documentation", "Alpha", "Zeta"]


def test_parent_traversal_pages_dropped(tmp_path):
    meta = {
        "ok/page": {"title": "Ok", "path": "ok/page", "group": "ok"},
        "../evil": {"title": "Evil", "path": "../evil", "group": "ok"},
        "a/../../evil2": {"title": "Evil2", "path": "a/../../evil2", "group": "ok"},
    }
    pages = [p for g in groups_of(build(tmp_path, meta)) for p in g["pages"]]
    assert pages == ["ok/page"]


def test_page_paths_normalised(tmp_path):
    meta = {"a\\b.mdx": {"title": "T", "path": "a\\b.mdx", "group": "a"}}
    pages = [p for g in groups_of(build(tmp_path, meta)) for p in g["pages"]]
    assert pages == ["a/b"]


@pytest.mark.parametrize("color", ["red", "#12", "#GGGGGG", "0D9373", "#0D93731234"])
def test_malformed_hex_color_raises(tmp_path, color):
    with pytest.raises(ValueError):
        generate_docs_json(META, tmp_path / "docs.json", primary_color=color)


def test_navbar_and_footer_placement(tmp_path):
    cfg = build(
        tmp_path,
        support_url="https://s.test",
        dashboard_url="https://d.test",
        twitter="https://x.com/o",
        github="https://github.com/o/r",
        linkedin="https://linkedin.com/in/o",
    )
    links = cfg["navbar"]["links"]
    assert any(l.get("href") == "https://s.test" for l in links)
    assert cfg["navbar"]["primary"]["href"] == "https://d.test"
    socials = cfg["footer"]["socials"]
    assert socials == {
        "x": "https://x.com/o",
        "github": "https://github.com/o/r",
        "linkedin": "https://linkedin.com/in/o",
    }


def test_navbar_footer_absent_when_unset(tmp_path):
    cfg = build(tmp_path)
    assert "navbar" not in cfg and "footer" not in cfg


def test_navbar_footer_valid_against_schema(tmp_path):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    cfg = build(
        tmp_path,
        support_url="https://s.test",
        dashboard_url="https://d.test",
        twitter="https://x.com/o",
        github="https://github.com/o/r",
    )
    jsonschema.validate(cfg, schema)


def test_symlinked_output_path_rejected(tmp_path):
    import os

    target = tmp_path / "real.json"
    target.write_text("{}")
    link = tmp_path / "docs.json"
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    with pytest.raises(ValueError):
        generate_docs_json(META, link)
    assert target.read_text() == "{}"
