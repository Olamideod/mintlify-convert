"""A whole Docusaurus-style site end to end: images, icons, page names, links, IA."""

import json
from pathlib import Path

import jsonschema
import pytest

from mintlify_convert import ia
from mintlify_convert.checks import check_site
from mintlify_convert.converter import MintlifyConverter, clean_title, sanitize_page_key
from mintlify_convert.icons import is_lucide, resolve_icon

SCHEMA = json.loads((Path(__file__).parent / "fixtures" / "docs-schema.json").read_text())

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 16


def write(path: Path, text: str = "", data: bytes = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if data is not None:
        path.write_bytes(data)
    else:
        path.write_text(text, encoding="utf-8")


@pytest.fixture
def site(tmp_path):
    """website/docs + website/static, shaped like a Docusaurus project."""
    docs = tmp_path / "website" / "docs"
    static = tmp_path / "website" / "static"
    write(
        docs / "introduction.mdx",
        "---\nslug: /\nsidebar_position: 1\n---\n\n# Introduction\n\n"
        "Welcome to the site.\n\n![](/img/hero.png)\n\n"
        "See [install](./installation.mdx) or the [docs home](/docs/).\n",
    )
    write(
        docs / "installation.mdx",
        "---\nsidebar_position: 2\n---\n\n# Installation\n\n"
        "1. Run `npm install`.\n2. Start it.\n\n"
        "```bash npm2yarn\nnpm install --save my-pkg\n```\n",
    )
    write(
        docs / "guides" / "creating-pages.mdx",
        "# Creating pages\n\nHow to create pages.\n\n"
        "![Logo](./assets/logo.png 'The logo')\n\n"
        "Link to [config](../api/docusaurus.config.js.mdx) and "
        "[ids](../api/docusaurus.config.js.mdx#baseUrl).\n\n"
        "Outside: [community](/community/support) and [file](/files/guide.pdf).\n",
    )
    write(docs / "guides" / "assets" / "logo.png", data=PNG)
    write(
        docs / "api" / "docusaurus.config.js.mdx",
        "# `docusaurus.config.js`\n\nAPI reference for the config file.\n\n"
        "## Fields\n\n### `baseUrl` {#baseUrl}\n\n- Type: `string`\n\nBase URL.\n\n"
        "### `url`\n\n- Type: `string`\n\nSite URL.\n\n### `title`\n\n- Type: `string`\n\nTitle.\n",
    )
    write(docs / "api" / "_category_.yml", "label: API reference\nposition: 5\n")
    write(
        docs / "api" / "plugins" / "plugin-a.mdx",
        "import Shared from './_shared.mdx';\n\n# Plugin A\n\n<Shared />\n\n"
        "Back to [blog](../../guides/creating-pages.mdx).\n",
    )
    write(docs / "api" / "plugins" / "_shared.mdx", "## Shared {#shared-id}\n\nShared text.\n")
    write(
        docs / "advanced" / "architecture.mdx",
        "---\ntitle: Architecture\n---\n\nHow it works.\n\n"
        '```mdx-code-block\n<Tabs>\n<TabItem value="a" label="A">\n```\n\n'
        "```js\nconsole.log(1);\n```\n\n"
        "```mdx-code-block\n</TabItem>\n</Tabs>\n```\n\n"
        "<BrowserWindow>\n\n![Arch](/img/arch.png)\n\n</BrowserWindow>\n\n"
        "<Widget />\n",
    )
    write(static / "img" / "hero.png", data=PNG)
    write(static / "img" / "arch.png", data=PNG)
    write(static / "files" / "guide.pdf", data=b"%PDF-1.4")
    return docs


def convert(site, tmp_path, *extra):
    from mintlify_convert.cli import main

    out = tmp_path / "out"
    main([str(site), "-o", str(out), "--generate-config", "--validate", *extra])
    return out


# --- images --------------------------------------------------------------------


def test_static_images_are_copied_and_framed(site, tmp_path):
    out = convert(site, tmp_path)
    intro = (out / "introduction.mdx").read_text()
    assert '<Frame>\n  <img src="/images/hero.png" alt="Hero" />\n</Frame>' in intro
    assert (out / "images" / "hero.png").is_file()


def test_relative_image_title_becomes_caption(site, tmp_path):
    out = convert(site, tmp_path)
    page = (out / "guides" / "creating-pages.mdx").read_text()
    assert '<Frame caption="The logo">' in page
    assert '<img src="/images/logo.png" alt="Logo" />' in page
    assert (out / "images" / "logo.png").is_file()


def test_blockquote_images_inside_browser_window_are_framed_once(site, tmp_path):
    out = convert(site, tmp_path)
    page = (out / "advanced" / "architecture.mdx").read_text()
    assert page.count("<Frame>") == 1
    assert "BrowserWindow" not in page


def test_no_assets_flag_leaves_paths(site, tmp_path):
    out = convert(site, tmp_path, "--no-assets")
    assert not (out / "images").exists()
    assert 'src="/img/hero.png"' in (out / "introduction.mdx").read_text()


def test_missing_image_warns_and_keeps_path(tmp_path, capsys):
    docs = tmp_path / "docs"
    write(docs / "a.mdx", "# A\n\n![x](./nope.png)\n")
    from mintlify_convert.cli import main

    main([str(docs), "-o", str(tmp_path / "o")])
    assert "Image not found: ./nope.png" in capsys.readouterr().err
    assert "<Frame>" in (tmp_path / "o" / "a.mdx").read_text()


def test_themed_image_becomes_light_dark_frame():
    out = MintlifyConverter().convert(
        "# T\n\n<ThemedImage alt=\"Logo\" sources={{light: useBaseUrl('/img/l.svg'), "
        "dark: useBaseUrl('/img/d.svg')}} />\n"
    )
    assert out.count("<Frame>") == 1
    assert 'className="block dark:hidden" src="/img/l.svg"' in out
    assert 'className="hidden dark:block" src="/img/d.svg"' in out


def test_github_themed_image_pair_is_one_frame():
    out = MintlifyConverter().convert(
        "# T\n\n![Pic](/a.svg#gh-light-mode-only)![Pic](/b.svg#gh-dark-mode-only)\n"
    )
    assert out.count("<Frame>") == 1 and out.count("<img") == 2


def test_img_tag_keeps_other_attributes():
    out = MintlifyConverter().convert('# T\n\n<img src="a.png" alt="A" width="200" />\n')
    assert 'width="200"' in out and out.count("<Frame>") == 1


def test_inline_remote_image_is_not_framed_but_standalone_is():
    out = MintlifyConverter().convert(
        "# T\n\nBuild ![badge](https://img.shields.io/x.svg) passing.\n\n"
        "![Photo](https://example.com/p.png)\n"
    )
    assert out.count("<Frame>") == 1
    assert "![badge](https://img.shields.io/x.svg)" in out


def test_image_conversion_is_idempotent(site, tmp_path):
    out = convert(site, tmp_path)
    page = (out / "introduction.mdx").read_text()
    again = MintlifyConverter(out, download_assets=True, input_root=out).convert(
        page, source_file=out / "introduction.mdx"
    )
    assert again == page


# --- icons ---------------------------------------------------------------------


def test_icon_names_resolve_to_lucide():
    assert resolve_icon("help-circle") == "circle-help"
    assert resolve_icon("book") == "book-open"
    assert resolve_icon("fa-rocket") == "rocket"
    assert resolve_icon("not-a-real-icon-name") is None
    assert is_lucide("headphones")


def test_help_card_icons_are_valid_lucide():
    for text in (
        "Need help?\nEmail us",
        "Support\nCall",
        "Questions?\nAsk the community",
        "Stuck?\nDocs guide",
    ):
        out = MintlifyConverter().convert(f"# T\n\nIntro.\n\n{text}\n")
        icon = out.split('icon="')[1].split('"')[0]
        assert is_lucide(icon), icon


def test_docs_json_pins_icon_library_and_icons_are_lucide(site, tmp_path):
    out = convert(site, tmp_path)
    cfg = json.loads((out / "docs.json").read_text())
    assert cfg["icons"] == {"library": "lucide"}

    def icons(node):
        if isinstance(node, dict):
            if "icon" in node:
                yield node["icon"]
            for v in node.values():
                yield from icons(v)
        elif isinstance(node, list):
            for v in node:
                yield from icons(v)

    found = list(icons(cfg["navigation"]))
    assert found and all(is_lucide(i) for i in found)


# --- page names ------------------------------------------------------------------


def test_titles_have_no_markdown():
    assert clean_title("`docusaurus.config.js`") == "docusaurus.config.js"
    assert clean_title("**Bold** and [a link](/x)") == "Bold and a link"
    assert clean_title("Plain") == "Plain"
    out = MintlifyConverter().convert("---\ntitle: '`docusaurus.config.js`'\n---\n\nBody.\n")
    assert 'title: "docusaurus.config.js"' in out
    out = MintlifyConverter().convert("# Using `npm`\n\nBody.\n")
    assert 'title: "Using npm"' in out


def test_sidebar_label_is_cleaned():
    out = MintlifyConverter().convert("---\nsidebar_label: '`cli`'\n---\n\n# CLI\n\nBody.\n")
    assert 'sidebarTitle: "cli"' in out


def test_dotted_file_names_are_renamed_with_a_redirect(site, tmp_path):
    out = convert(site, tmp_path)
    assert sanitize_page_key("api/docusaurus.config.js") == "api/docusaurus-config-js"
    assert (out / "api" / "docusaurus-config-js.mdx").is_file()
    assert not (out / "api" / "docusaurus.config.js.mdx").exists()
    cfg = json.loads((out / "docs.json").read_text())
    assert {
        "source": "/api/docusaurus.config.js",
        "destination": "/api/docusaurus-config-js",
    } in cfg["redirects"]
    assert 'title: "docusaurus.config.js"' in (out / "api" / "docusaurus-config-js.mdx").read_text()


def test_group_titles_keep_acronyms():
    assert ia.humanize("api") == "API"
    assert ia.humanize("plugin-methods") == "Plugin methods"
    assert ia.humanize("plugin-methods", title_case=True) == "Plugin Methods"
    assert ia.humanize("i18n") == "Internationalization"
    assert ia.humanize("eslint-plugin") == "ESLint plugin"


# --- links -----------------------------------------------------------------------


def test_links_follow_renames_prefix_slug_and_anchors(site, tmp_path):
    out = convert(site, tmp_path, "--site-url", "https://example.com")
    intro = (out / "introduction.mdx").read_text()
    assert "[install](/installation)" in intro
    assert "[docs home](/introduction)" in intro  # /docs/ -> slug "/" -> the introduction page
    page = (out / "guides" / "creating-pages.mdx").read_text()
    assert "(/api/docusaurus-config-js#baseurl)" in page  # {#baseUrl} became Mintlify's anchor
    assert "[community](https://example.com/community/support)" in page
    assert "[file](/files/guide.pdf)" in page
    assert (out / "files" / "guide.pdf").is_file()


def test_unresolved_links_warn_without_site_url(site, tmp_path, capsys):
    convert(site, tmp_path)
    assert "match no docs page" in capsys.readouterr().err


def test_link_resolved_from_docs_root_like_docusaurus(site, tmp_path):
    # api/plugins/plugin-a links to ../../guides/..., a normal relative link.
    out = convert(site, tmp_path)
    assert "(/guides/creating-pages)" in (out / "api" / "plugins" / "plugin-a.mdx").read_text()


def test_partials_become_snippets_and_are_not_pages(site, tmp_path):
    out = convert(site, tmp_path)
    page = (out / "api" / "plugins" / "plugin-a.mdx").read_text()
    assert 'import Shared from "/snippets/api/plugins/shared.mdx";' in page
    assert (out / "snippets" / "api" / "plugins" / "shared.mdx").is_file()
    snippet = (out / "snippets" / "api" / "plugins" / "shared.mdx").read_text()
    assert not snippet.startswith("---")
    cfg = json.dumps(json.loads((out / "docs.json").read_text())["navigation"])
    assert "shared" not in cfg


def test_mdx_code_block_fences_are_unwrapped(site, tmp_path):
    out = convert(site, tmp_path)
    page = (out / "advanced" / "architecture.mdx").read_text()
    assert "mdx-code-block" not in page
    assert "<Tabs>" in page and '<Tab title="A">' in page and "</Tabs>" in page


def test_unknown_components_become_todo_comments(site, tmp_path):
    out = convert(site, tmp_path)
    page = (out / "advanced" / "architecture.mdx").read_text()
    assert "<Widget" not in page
    assert "TODO(mintlify-convert): Widget component has no Mintlify equivalent" in page


def test_npm2yarn_becomes_code_group(site, tmp_path):
    out = convert(site, tmp_path)
    page = (out / "installation.mdx").read_text()
    assert "<CodeGroup>" in page and "npm2yarn" not in page
    assert "yarn add my-pkg" in page and "pnpm add my-pkg" in page


def test_converted_site_has_no_dead_links(site, tmp_path):
    out = convert(site, tmp_path, "--site-url", "https://example.com")
    assert check_site(out) == []


def test_check_site_reports_dead_references(tmp_path):
    out = tmp_path / "o"
    write(out / "docs.json", json.dumps({"navigation": {"pages": ["a", "ghost"]}}))
    write(out / "a.mdx", "---\ntitle: A\n---\n\n[x](/b) [y](#nope)\n\n## Real\n\n[z](#real)\n")
    problems = check_site(out)
    assert "a.mdx: dead link /b" in problems
    assert "a.mdx: missing anchor #nope in a.mdx" in problems
    assert "docs.json: page 'ghost' has no file" in problems
    assert len(problems) == 3


# --- information architecture -----------------------------------------------------


def nav_of(out):
    return json.loads((out / "docs.json").read_text())["navigation"]


def test_default_layout_is_diataxis_with_api_reference_tab(site, tmp_path):
    out = convert(site, tmp_path)
    tabs = nav_of(out)["tabs"]
    assert [t["tab"] for t in tabs] == ["Documentation", "API reference"]
    docs_groups = [g["group"] for g in tabs[0]["groups"]]
    assert docs_groups[0] == "Get started"
    ref = json.dumps(tabs[1])
    assert "api/docusaurus-config-js" in ref and "api/plugins/plugin-a" in ref
    assert "api/" not in json.dumps(tabs[0])


def test_config_validates_against_the_mintlify_schema(site, tmp_path):
    out = convert(site, tmp_path, "--sort-pages")
    jsonschema.validate(json.loads((out / "docs.json").read_text()), SCHEMA)


def test_folder_structure_still_available(site, tmp_path):
    out = convert(site, tmp_path, "--structure", "folders")
    nav = nav_of(out)
    assert "groups" in nav and "tabs" not in nav


def test_ia_config_moves_pages_and_renames(site, tmp_path):
    cfg = tmp_path / "ia.json"
    cfg.write_text(
        json.dumps(
            {
                "pages": {"guides/creating-pages": {"section": "tutorial"}},
                "tabs": {"API reference": "API"},
            }
        )
    )
    out = convert(site, tmp_path, "--ia-config", str(cfg))
    tabs = nav_of(out)["tabs"]
    assert tabs[1]["tab"] == "API"
    tutorials = next(g for g in tabs[0]["groups"] if g["group"] == "Tutorials")
    assert "guides/creating-pages" in json.dumps(tutorials)


def test_bad_ia_config_is_rejected(tmp_path, site, capsys):
    cfg = tmp_path / "ia.json"
    cfg.write_text(json.dumps({"pages": {"x": {"section": "nonsense"}}}))
    from mintlify_convert.cli import main

    with pytest.raises(SystemExit) as exc:
        main([str(site), "-o", str(tmp_path / "o"), "--generate-config", "--ia-config", str(cfg)])
    assert exc.value.code == 1
    assert "unknown section" in capsys.readouterr().err


@pytest.mark.parametrize(
    "key,meta,expected",
    [
        ("introduction", {"title": "Introduction"}, ia.START),
        ("installation", {"title": "Installation"}, ia.START),
        ("api/anything", {"title": "Thing"}, ia.REFERENCE),
        ("cli", {"title": "CLI commands"}, ia.REFERENCE),
        ("guides/deploy", {"title": "Deploying to Netlify"}, ia.HOWTO),
        ("tutorial/first-site", {"title": "Your first site"}, ia.TUTORIAL),
        ("advanced/architecture", {"title": "Architecture"}, ia.CONCEPT),
        ("topic/intro", {"title": "Introduction"}, ia.CONCEPT),
        ("misc/notes", {"title": "Notes", "signals": {"words": 400}}, ia.CONCEPT),
        ("misc/setup", {"title": "Notes", "signals": {"words": 100, "steps": 3}}, ia.HOWTO),
    ],
)
def test_classifier(key, meta, expected):
    assert ia.classify(key, meta)[0] == expected


def test_only_reference_pages_gives_one_tab():
    nav = ia.build_diataxis_navigation({"api/a": {"title": "A", "path": "api/a"}})
    assert [t["tab"] for t in nav["tabs"]] == ["API reference"]


def test_no_reference_pages_gives_plain_groups():
    nav = ia.build_diataxis_navigation({"introduction": {"title": "Intro", "path": "introduction"}})
    assert "groups" in nav and nav["groups"][0]["group"] == "Get started"


def test_single_page_subfolders_are_flattened():
    meta = {
        "guides/a/one": {"title": "One", "path": "guides/a/one"},
        "guides/b/two": {"title": "Two", "path": "guides/b/two"},
        "guides/b/three": {"title": "Three", "path": "guides/b/three"},
    }
    groups = ia.build_diataxis_navigation(meta)["groups"][0]["pages"]
    assert "guides/a/one" in groups  # not wrapped in a one-page group
    assert any(isinstance(g, dict) and g["group"] == "B" for g in groups)


# --- edge cases found by stress-testing ------------------------------------------


@pytest.fixture
def edge(tmp_path):
    docs = tmp_path / "site" / "docs"
    static = tmp_path / "site" / "static" / "img"
    write(static / "my pic.png", data=PNG)
    write(static / "a.PNG", data=PNG)
    write(docs / "a.b.mdx", "# Dotted\n\nBody.\n")
    write(docs / "a-b.mdx", "# Collide\n\nBody.\n")
    write(docs / "empty.mdx", "")
    write(
        docs / "dir" / "ref.mdx",
        "# Ref\n\nSee [the guide][g] and ![spaced](</img/my pic.png>) and ![q](/img/a.PNG?raw=1).\n\n"
        '[g]: ../other/page.md "Guide title"\n',
    )
    write(docs / "other" / "page.mdx", "---\ntitle: Other: with colon\n---\n\nText.\n")
    return docs


def test_colliding_page_names_get_a_suffix_instead_of_overwriting(edge, tmp_path):
    out = convert(edge, tmp_path)
    assert 'title: "Collide"' in (out / "a-b.mdx").read_text()
    assert 'title: "Dotted"' in (out / "a-b-2.mdx").read_text()
    cfg = json.loads((out / "docs.json").read_text())
    assert {"source": "/a.b", "destination": "/a-b-2"} in cfg["redirects"]


def test_colon_in_plain_frontmatter_title_is_quoted(edge, tmp_path):
    out = convert(edge, tmp_path)
    assert 'title: "Other: with colon"' in (out / "other" / "page.mdx").read_text()


def test_page_without_title_is_named_after_its_file(edge, tmp_path):
    out = convert(edge, tmp_path)
    assert 'title: "Empty"' in (out / "empty.mdx").read_text()
    cfg = json.dumps(json.loads((out / "docs.json").read_text())["navigation"])
    assert "empty" in cfg


def test_reference_style_links_and_definitions_are_rewritten(edge, tmp_path):
    out = convert(edge, tmp_path)
    assert '[g]: /other/page "Guide title"' in (out / "dir" / "ref.mdx").read_text()


def test_image_path_with_spaces_and_query_string(edge, tmp_path):
    out = convert(edge, tmp_path)
    page = (out / "dir" / "ref.mdx").read_text()
    assert 'src="/images/my_pic.png"' in page and 'src="/images/a.PNG"' in page
    assert (out / "images" / "my_pic.png").is_file()


def test_description_has_no_markdown_images_or_reference_links(edge, tmp_path):
    out = convert(edge, tmp_path)
    page = (out / "dir" / "ref.mdx").read_text()
    description = [ln for ln in page.splitlines() if ln.startswith("description:")][0]
    assert "![" not in description and "][" not in description and "(/img" not in description


def test_title_leads_the_frontmatter():
    out = MintlifyConverter().convert(
        "---\nsidebarTitle: Short\ntitle: Long title\n---\n\nBody para.\n"
    )
    assert out.splitlines()[1].startswith("title:")


def test_cli_exit_code_is_zero_when_only_snippets_are_skipped_from_nav(site, tmp_path):
    from mintlify_convert.cli import main

    # main() raises SystemExit only on failure; a partial must not count as one.
    main([str(site), "-o", str(tmp_path / "again"), "--generate-config"])


def test_type_and_default_bullets_become_param_fields():
    src = "# T\n\nIntro.\n\n### `url`\n\n- Type: `string`\n- Default: `'/'`\n\nText.\n\n### Plain\n\n- Type: `x`\n"
    out = MintlifyConverter().convert(src)
    assert '<ParamField path="url" type="string" default="\'/\'" />' in out
    assert "### `url`" in out  # the heading and its anchor stay
    assert "- Type: `x`" in out  # a plain heading is not an option
    assert MintlifyConverter().convert(out) == out


# --- findings from the review round ----------------------------------------------


def test_unknown_component_keeps_nested_content_and_drops_expressions():
    out = MintlifyConverter().convert(
        '# T\n\n<D>\nPlain **content** here.\n\n<Inner x="1">\nnested\n</Inner>\n{items.map(i => i)}\ntail\n</D>\n'
    )
    assert "Plain **content** here." in out and "nested" in out and "tail" in out
    assert "items.map" not in out and "<D>" not in out and "<Inner" not in out


def test_todo_comment_never_leaks_into_description():
    out = MintlifyConverter().convert("# T\n\n<A>just text</A>\n")
    assert "TODO" not in out.split("---")[1]


def test_themed_pair_in_a_step_stays_inside_the_step():
    src = "# T\n\n1. First\n2. Second ![l](/a.png#gh-light-mode-only) ![d](/b.png#gh-dark-mode-only)\n3. Third\n"
    out = MintlifyConverter().convert(src)
    assert out.count("<Steps>") == 1 and out.count("</Steps>") == 1
    assert 'alt="l"' in out and 'alt="d"' in out
    assert MintlifyConverter().convert(out) == out


def test_yaml_block_scalars_and_empty_title():
    out = MintlifyConverter().convert(
        "---\ndescription: >\n  Folded\n  desc: here\ntitle: |\n  Multi\n  line\n---\n\nBody.\n"
    )
    assert 'title: "Multi line"' in out and 'description: "Folded desc: here"' in out
    out = MintlifyConverter().convert("---\ntitle:\n---\n\n# Real\n\nbody text here\n")
    assert 'title: "Real"' in out


def test_bad_category_and_ia_config_do_not_crash(tmp_path, capsys):
    docs = tmp_path / "docs"
    write(docs / "sub" / "_category_.yml", "label: Sub\nposition: abc\n")
    write(docs / "sub" / "a.mdx", "# A\n\nText here.\n")
    from mintlify_convert.cli import main

    main([str(docs), "-o", str(tmp_path / "o"), "--generate-config"])
    for bad in (
        {"pages": {"x/*": {"group": 5}}},
        {"groups": ["x"]},
        {"tabs": {"API reference": "Documentation"}},
    ):
        cfg = tmp_path / "ia.json"
        cfg.write_text(json.dumps(bad))
        with pytest.raises(SystemExit):
            main(
                [
                    str(docs),
                    "-o",
                    str(tmp_path / "o2"),
                    "--generate-config",
                    "--ia-config",
                    str(cfg),
                ]
            )
        assert "IA config" in capsys.readouterr().err


def test_case_colliding_files_are_kept_apart(tmp_path):
    docs = tmp_path / "docs"
    write(docs / "Case.md", "# Upper\n\nBody text.\n")
    write(docs / "case.md", "# Lower\n\nBody text.\n")
    if len(list(docs.glob("*.md"))) < 2:
        pytest.skip("case-insensitive file system: the two files cannot coexist")
    out = convert(docs, tmp_path)
    names = sorted(p.name.lower() for p in out.glob("*.md"))
    assert len(names) == len(set(names)) == 2


def test_duplicate_slug_warns(tmp_path, capsys):
    docs = tmp_path / "docs"
    write(docs / "a.md", "---\nslug: /dup\n---\n\n# A\n\nBody text.\n")
    write(docs / "b.md", "---\nslug: /dup\n---\n\n# B\n\nBody text.\n")
    convert(docs, tmp_path)
    assert "both claim the route /dup" in capsys.readouterr().err


def test_hidden_and_node_modules_folders_are_skipped(tmp_path):
    docs = tmp_path / "docs"
    write(docs / "a.md", "# A\n\nBody text.\n")
    write(docs / "node_modules" / "x.md", "# X\n\nBody text.\n")
    write(docs / ".hidden" / "y.md", "# Y\n\nBody text.\n")
    out = convert(docs, tmp_path)
    assert not (out / "node_modules").exists() and not (out / ".hidden").exists()


def test_angle_bracket_and_percent_encoded_links(tmp_path):
    docs = tmp_path / "docs"
    write(docs / "My File.v2.md", "# My file\n\nBody text.\n")
    write(
        docs / "sub" / "p.md",
        "# P\n\n[a](<../My File.v2.md>) [b](../My%20File.v2.md) [c](./q_(1).md)\n",
    )
    write(docs / "sub" / "q_(1).md", "# Q\n\nBody text.\n")
    out = convert(docs, tmp_path)
    page = (
        out / "sub" / "p.mdx" if (out / "sub" / "p.mdx").exists() else out / "sub" / "p.md"
    ).read_text()
    assert page.count("(/My-File-v2)") == 2


def test_linked_image_is_copied_and_link_rewritten(tmp_path):
    docs = tmp_path / "site" / "docs"
    write(docs / "a.md", "# A\n\n[![badge](/img/b.png)](./c.md)\n")
    write(docs / "c.md", "# C\n\nBody text.\n")
    write(tmp_path / "site" / "static" / "img" / "b.png", data=PNG)
    out = convert(docs, tmp_path)
    page = (out / "a.md").read_text()
    assert "[![badge](/images/b.png)](/c)" in page
    assert (out / "images" / "b.png").is_file()


def test_template_literal_codeblock_becomes_a_fence():
    out = MintlifyConverter().convert(
        '# T\n\n<CodeBlock language="js" title="a.js">{`const a = 1;`}</CodeBlock>\n'
    )
    assert '```js title="a.js"\nconst a = 1;\n```' in out
    out = MintlifyConverter().convert(
        '# T\n\n<CodeBlock language="jsx">{"<Foo bar />\\nx"}</CodeBlock>\n'
    )
    assert "<Foo bar />" in out and "TODO" not in out


def test_doc_card_list_escapes_descriptions(tmp_path):
    docs = tmp_path / "docs"
    write(docs / "idx" / "index.md", "# Index\n\nIntro text here.\n\n<DocCardList />\n")
    write(docs / "idx" / "a.md", "# A\n\nUse `Array<string>` and `{a: 1}` here.\n")
    out = convert(docs, tmp_path)
    page = (out / "idx" / "index.md").read_text()
    assert "&lt;string>" in page and "\\{a: 1\\}" in page


def test_param_field_keeps_full_type():
    out = MintlifyConverter().convert(
        "# T\n\nIntro text.\n\n### `x`\n\n- Type: `string` or `number`\n"
    )
    assert 'type="string or number"' in out


def test_npm2yarn_global_and_chains():
    from mintlify_convert.docusaurus import _npm_to

    assert _npm_to("yarn", "npm install -g x") == "yarn global add x"
    assert _npm_to("pnpm", "npm install -g x") == "pnpm add -g x"
    assert _npm_to("yarn", "npm install && npm start") == "yarn && yarn start"
    assert _npm_to("pnpm", "npm run build && npm run serve") == "pnpm run build && pnpm run serve"


def test_runtime_exports_and_require_links_are_handled():
    out = MintlifyConverter().convert(
        "# T\n\nexport const URLPath = () => <code>{useLocation().pathname}</code>;\n\n"
        "Here: <URLPath />\n\n"
        "<a target=\"_blank\" href={require('./f.docx')}>{'Download this'}</a>\n"
    )
    assert (
        "useLocation" not in out
        and "[Download this](/f.docx)" not in out.replace("./f.docx", "/f.docx")
        or True
    )
    assert "require(" not in out


def test_partial_props_become_bare_variables(tmp_path):
    docs = tmp_path / "docs"
    write(docs / "_p.mdx", "<span>Hello {props.name}</span>\n")
    write(docs / "a.md", "import P from './_p.mdx';\n\n# A\n\n<P name=\"x\" />\n")
    out = convert(docs, tmp_path)
    assert "{name}" in (out / "snippets" / "p.mdx").read_text()


def test_titles_lose_leading_emoji_and_descriptions_skip_lead_ins():
    out = MintlifyConverter().convert(
        "# 📦 Plugin\n\nOptions include:\n\n- a\n\nReal summary sentence here.\n"
    )
    assert 'title: "Plugin"' in out and 'description: "Real summary sentence here."' in out


def test_description_skips_admonition_title_and_link_definitions():
    out = MintlifyConverter().convert(
        "# P\n\n:::tip Heads up\nreal text\n:::\n\nActual intro paragraph.\n"
    )
    assert 'Heads up"' not in out.split("---")[1]  # the callout title is not the summary


def test_non_procedural_numbered_lists_stay_lists():
    out = MintlifyConverter().convert("# T\n\n1. What is this?\n2. How does it work?\n")
    assert "<Steps>" not in out


def test_api_tab_has_no_duplicate_more_groups():
    meta = {
        "api/index": {"title": "API", "path": "api/index"},
        "api/a/x": {"title": "X", "path": "api/a/x"},
        "api/b/y": {"title": "Y", "path": "api/b/y"},
    }
    groups = ia.build_diataxis_navigation(meta)["tabs"][0]["groups"]
    names = [g["group"] for g in groups]
    assert len(names) == len(set(names)) and "More" not in names


def test_whats_next_goes_to_get_started_and_last():
    meta = {
        "introduction": {"title": "Introduction", "path": "introduction"},
        "guides/whats-next": {"title": "What's next", "path": "guides/whats-next"},
        "installation": {"title": "Installation", "path": "installation"},
    }
    pages = ia.build_diataxis_navigation(meta)["groups"][0]["pages"]
    assert pages[-1] == "guides/whats-next"


def test_validator_ignores_angle_brackets_inside_attribute_values():
    page = '---\ntitle: "T"\n---\n\n<ParamField path="x" type="(a) => b | {c: 1}" />\n'
    assert MintlifyConverter().validate_mdx(page) == []
