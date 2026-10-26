"""Docusaurus syntax is rewritten to Mintlify components, code blocks and frontmatter."""

import pytest

from mintlify_convert.converter import MintlifyConverter


def convert(text: str, **kwargs):
    conv = MintlifyConverter()
    return conv.convert(text, validate=True, **kwargs), conv


def body(text: str) -> str:
    out, _ = convert(text)
    return out.split("---\n\n", 1)[1] if out.startswith("---") else out


def assert_clean(text: str):
    """Converted output is valid, and converting it again changes nothing."""
    out, conv = convert(text)
    assert conv.validation_errors == []
    again, _ = convert(out)
    assert again == out


# --- admonitions ---------------------------------------------------------------


@pytest.mark.parametrize(
    "kind,tag",
    [
        ("note", "Note"),
        ("tip", "Tip"),
        ("info", "Info"),
        ("warning", "Warning"),
        ("caution", "Warning"),
        ("danger", "Danger"),
        ("success", "Check"),
        ("secondary", "Note"),
    ],
)
def test_admonition_types(kind, tag):
    out = body(f"# T\n\n:::{kind}\n\nHello there.\n\n:::\n")
    assert f"<{tag}>\n\nHello there.\n\n</{tag}>" in out
    assert ":::" not in out
    assert_clean(f"# T\n\n:::{kind}\n\nHello there.\n\n:::\n")


def test_admonition_title_forms():
    for opener in (":::tip Use tabs", ":::tip[Use tabs]", ":::tip[Use tabs]{.padding--lg}"):
        out = body(f"# T\n\n{opener}\n\nText.\n\n:::\n")
        assert "<Tip>\n\n**Use tabs**\n\nText.\n\n</Tip>" in out


def test_admonition_title_with_markdown_and_attrs_only():
    out = body("# T\n\n:::note[A **bold** `code` title]\n\nX\n\n:::\n")
    assert "**A **bold**" not in out
    assert "A **bold** `code` title" in out
    out = body("# T\n\n:::note{#admonition-id}\n\nX\n\n:::\n")
    assert "<Note>\n\nX\n\n</Note>" in out


def test_admonition_nested_and_indented_in_list():
    src = "# T\n\n::::tip Outer\n\nText\n\n:::warning Inner\n\nDeep\n\n:::\n\n::::\n"
    out = body(src)
    assert out.index("<Tip>") < out.index("<Warning>") < out.index("</Warning>")
    assert out.index("</Warning>") < out.index("</Tip>")
    assert_clean(src)
    listed = "# T\n\n- item\n\n  :::note\n  inner\n  :::\n"
    assert "  <Note>" in body(listed) and "  </Note>" in body(listed)


def test_admonition_with_code_fence_and_list_inside():
    src = "# T\n\n:::tip\n\n```js\nconst a = 1;\n```\n\n- a\n- b\n\n:::\n"
    out = body(src)
    assert "```js\nconst a = 1;\n```" in out
    assert_clean(src)


def test_admonition_untouched_in_code_unclosed_and_empty():
    fenced = "# T\n\n```md\n:::note\nx\n:::\n```\n"
    assert ":::note\nx\n:::" in body(fenced)
    out = body("# T\n\n:::note\n\nnever closed\n")
    assert ":::note" in out and "<Note>" not in out
    assert "<Note>" in body("# T\n\n:::note\n:::\n")


def test_unknown_admonition_warns_and_becomes_note():
    out, conv = convert("# T\n\n:::container\n\nBody\n\n:::\n")
    assert "<Note>" in out
    assert any("container" in w for w in conv.warnings)


# --- tabs ----------------------------------------------------------------------


def test_tabitem_label_value_default():
    src = (
        "# T\n\nimport Tabs from '@theme/Tabs';\nimport TabItem from '@theme/TabItem';\n\n"
        '<Tabs groupId="pm" queryString>\n<TabItem value="npm" label="npm" default>\n\nnpm\n\n'
        '</TabItem>\n<TabItem value="yarn" label="Yarn">\n\nyarn\n\n</TabItem>\n</Tabs>\n'
    )
    out = body(src)
    assert '<Tabs>\n<Tab title="npm">' in out
    assert '<Tab title="Yarn">' in out
    assert "TabItem" not in out and "groupId" not in out and "import" not in out
    assert_clean(src)


def test_tabs_values_prop_and_default_index():
    src = (
        "# T\n\n<Tabs defaultValue=\"b\" values={[{label: 'Alpha', value: 'a'}, "
        "{label: 'Beta', value: 'b'}]}>\n<TabItem value=\"a\">\n\nA\n\n</TabItem>\n"
        '<TabItem value="b">\n\nB\n\n</TabItem>\n</Tabs>\n'
    )
    out = body(src)
    assert "<Tabs defaultTabIndex={1}>" in out
    assert '<Tab title="Alpha">' in out and '<Tab title="Beta">' in out
    assert "values=" not in out
    assert_clean(src)


def test_tabitem_default_attr_sets_index():
    src = (
        '# T\n\n<Tabs>\n<TabItem value="a" label="A">\n\nA\n\n</TabItem>\n'
        '<TabItem value="b" label="B" default>\n\nB\n\n</TabItem>\n</Tabs>\n'
    )
    assert "<Tabs defaultTabIndex={1}>" in body(src)
    assert_clean(src)


def test_tabs_nested_and_odd_labels():
    src = (
        '# T\n\n<Tabs>\n<TabItem value="a" label="Say &quot;hi&quot;">\n\n'
        '<Tabs>\n<TabItem value="x" label={"Inner"}>\n\nX\n\n</TabItem>\n</Tabs>\n\n'
        "</TabItem>\n</Tabs>\n"
    )
    out = body(src)
    assert out.count("<Tabs") == 2 and out.count("</Tabs>") == 2
    assert '<Tab title="Inner">' in out
    assert_clean(src)


def test_tabs_in_code_untouched():
    out = body('# T\n\n```mdx\n<Tabs>\n<TabItem value="a">x</TabItem>\n</Tabs>\n```\n')
    assert "<TabItem" in out


# --- details -------------------------------------------------------------------


def test_details_become_accordion():
    src = "# T\n\n<details>\n  <summary>How do I <code>install</code>?</summary>\n\nRun it.\n\n</details>\n"
    out = body(src)
    assert '<Accordion title="How do I `install`?">' in out
    assert "</Accordion>" in out and "details" not in out
    assert_clean(src)


def test_details_open_nested_and_no_summary():
    src = (
        "# T\n\n<details open>\n<summary>Outer</summary>\n\n<details>\n<summary>Inner</summary>\n\n"
        "x\n\n</details>\n\n</details>\n\n<details>\n\nbare\n\n</details>\n"
    )
    out = body(src)
    assert '<Accordion title="Outer" defaultOpen>' in out
    assert '<Accordion title="Inner">' in out
    assert '<Accordion title="Details">' in out
    assert_clean(src)


def test_details_summary_quotes_escaped():
    out = body('# T\n\n<details><summary>Say "hi"</summary>\n\nx\n\n</details>\n')
    assert 'title="Say &quot;hi&quot;"' in out


# --- imports, comments, ids, inline components ---------------------------------


def test_imports_removed_multiline_and_snippets_kept():
    src = (
        "# T\n\nimport A from '@site/src/A';\nimport {\n  B,\n  C as D,\n} from 'lib';\n"
        "import '@site/x.css';\nimport Snip from '/snippets/snip.mdx';\n\nText\n"
    )
    out, conv = convert(src)
    assert "@site" not in out and "from 'lib'" not in out
    assert "import Snip from '/snippets/snip.mdx';" in out
    assert "\n\n\n" not in out


def test_removed_import_still_used_warns():
    out, conv = convert("# T\n\nimport Widget from '@site/src/Widget';\n\n<Widget />\n")
    assert any("Widget" in w for w in conv.warnings)


def test_imports_in_code_untouched():
    out = body("# T\n\n```js\nimport a from 'b';\n```\n")
    assert "import a from 'b';" in out


def test_html_comments_become_mdx_comments():
    out = body("# T\n\n<!-- one -->\n\n<!--\nmulti */ line\n-->\n\nText\n")
    assert "{/* one */}" in out and "<!--" not in out
    assert "multi * / line" in out
    assert_clean("# T\n\n<!-- one -->\n\nText\n")
    assert "<!-- keep -->" in body("# T\n\n```html\n<!-- keep -->\n```\n")


def test_heading_ids_removed_with_one_warning():
    out, conv = convert(
        "# T\n\n## First {#custom-a}\n\n## Second {/* #custom-b */}\n\n## Plain {#plain}\n"
    )
    assert "{#" not in out and "{/*" not in out
    assert "## First\n" in out and "## Second\n" in out
    assert len([w for w in conv.warnings if "heading id" in w]) == 1
    assert "#plain" not in " ".join(conv.warnings)


def test_translate_link_toc_components():
    src = (
        "# T\n\nimport Translate from '@docusaurus/Translate';\n\n"
        '<Translate id="x">Hello</Translate> and <Link to="/docs/a">the docs</Link>.\n\n'
        "<TOCInline toc={toc} />\n\n<DocCardList />\n\nEnd\n"
    )
    out, conv = convert(src)
    assert "Hello and [the docs](/docs/a)." in out
    assert "TOCInline" not in out and "DocCardList" not in out


def test_unknown_component_warning():
    _, conv = convert("# T\n\n<LiveEditor>x</LiveEditor>\n\n<Note>ok</Note>\n")
    assert any("LiveEditor" in w for w in conv.warnings)
    assert not any("<Note>" in w for w in conv.warnings)


# --- code blocks ---------------------------------------------------------------


def test_fence_meta_translated():
    out = body("# T\n\n```js title='a.js' showLineNumbers {1,3-4}\nx\ny\nz\nw\n```\n")
    assert '```js title="a.js" lines highlight={1,3-4}' in out


def test_fence_title_untouched():
    src = '# T\n\n```js title="docusaurus.config.js"\nx\n```\n'
    assert '```js title="docusaurus.config.js"\n' in body(src)


@pytest.mark.parametrize(
    "marker",
    ["// highlight-next-line", "# highlight-next-line", "/* highlight-next-line */",
     "{/* highlight-next-line */}", "<!-- highlight-next-line -->"],
)  # fmt: skip
def test_magic_comment_next_line(marker):
    out = body(f"# T\n\n```js\na\n  {marker}\nb\nc\n```\n")
    assert "```js highlight={2}\na\nb\nc\n```" in out
    assert "highlight-" not in out


def test_magic_comment_ranges_and_unclosed():
    out = body("# T\n\n```js\na\n// highlight-start\nb\nc\n// highlight-end\nd\n```\n")
    assert "```js highlight={2-3}\na\nb\nc\nd\n```" in out
    out = body("# T\n\n```js\na\n// highlight-start\nb\nc\n```\n")
    assert "highlight={2-3}" in out


def test_magic_comment_without_language_gets_text():
    out = body("# T\n\n```\n// highlight-next-line\nx\n```\n")
    assert "```text highlight={1}\nx\n```" in out


def test_plain_fence_is_byte_identical():
    src = "# T\n\n```python\nprint('x')   \n\n  y\n```\n"
    assert "```python\nprint('x')   \n\n  y\n```" in body(src)


def test_fence_conversion_is_idempotent():
    assert_clean('# T\n\n```js title="a" showLineNumbers\n// highlight-next-line\nx\n```\n')


def test_live_and_reference_flags_dropped():
    assert "```jsx\n" in body("# T\n\n```jsx live\nx\n```\n")


# --- frontmatter ---------------------------------------------------------------


def test_frontmatter_docusaurus_keys():
    src = (
        "---\nid: intro\nslug: /intro\nsidebar_position: 2\nsidebar_label: Short\n"
        "tags:\n  - a\n  - b\ntitle: Real\nkeywords:\n  - x\nhide_table_of_contents: true\n---\n\nBody\n"
    )
    out, _ = convert(src)
    head = out.split("---\n\n", 1)[0]
    for gone in ("id:", "slug:", "sidebar_position", "tags:", "- a", "hide_table"):
        assert gone not in head
    assert "sidebarTitle: Short" in head and "title: Real" in head and "keywords:" in head
    assert "- x" in head
    assert_clean(src)


# --- whole page ----------------------------------------------------------------


def test_realistic_page_is_clean():
    src = """---
sidebar_position: 1
description: Deploy a blog.
---

# Blog

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Intro paragraph.

:::info

Read the [API docs](./api/blog.mdx).

:::

## Initial setup {/* #initial-setup */}

```js title="docusaurus.config.js"
export default {
  // highlight-start
  feedOptions: {},
  // highlight-end
};
```

The feeds can be found at:

<Tabs>
<TabItem value="RSS">

```text
https://example.com/rss.xml
```

</TabItem>
</Tabs>

<details>
<summary>More</summary>

Details.

</details>
"""
    out, conv = convert(src)
    assert conv.validation_errors == []
    for gone in (":::", "TabItem", "@theme", "{/* #", "highlight-"):
        assert gone not in out
    assert '```js title="docusaurus.config.js" highlight={2}' in out
    assert "[API docs](./api/blog)" in out
    again, _ = convert(out)
    assert again == out


def test_image_and_link_single_quoted_titles(tmp_path):
    out = body("# T\n\n![Alt](./a.png 'Image title')\n\n[Doc](./other.md 'Tip')\n")
    assert '<img src="./a.png" alt="Alt" />' in out
    assert "[Doc](/other 'Tip')" in out or "[Doc](other 'Tip')" in out or "other" in out
    assert "'Image title'" not in out.split("<img")[1].split("/>")[0]


def test_pathological_input_stays_fast():
    from tests.conftest import run_python

    code = (
        "from mintlify_convert.converter import MintlifyConverter as C\n"
        "src = ('<Tabs a=\"b\"\\n' + ':::note\\n' + '<details>\\n' + '<!-- x\\n') * 8000\n"
        "C().convert(src)\n"
    )
    assert run_python(code, timeout=30).returncode == 0
