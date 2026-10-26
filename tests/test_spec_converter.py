"""Behavior-spec tests for the converter (fences, frontmatter, idempotence,
descriptions, steps, links, callouts, tabs, banner, frames, validation)."""

import re

import pytest

from mintlify_convert.converter import MintlifyConverter

from .conftest import FIXTURES


@pytest.fixture
def conv():
    return MintlifyConverter()


def split_frontmatter(text):
    """Return (frontmatter_text, body). Fails if there is not exactly one block."""
    assert text.startswith("---\n"), f"no frontmatter: {text[:60]!r}"
    end = text.index("\n---", 3)
    return text[4:end], text[end + 4 :]


# --- 1. fenced code is never transformed -----------------------------------

FENCE_BODY = (
    "1. one\n2. two\n3. three\n"
    "> Note: keep this quote\n"
    "[a link](other.md)\n"
    "![img](pic.png)\n"
    "JavaScript:\nconst x = 1;\n\nPython:\nx = 1\n"
    "### Advanced Section\n"
)


@pytest.mark.parametrize("fence", ["```", "~~~", "````"])
def test_fenced_code_untouched(conv, fence):
    block = f"{fence}\n{FENCE_BODY}{fence}"
    result = conv.convert(f"# T\n\nIntro text.\n\n{block}\n\nAfter.\n")
    assert block in result


def test_fence_with_language_info_string_untouched(conv):
    block = "```markdown\n1. one\n2. two\n> Warning: x\n```"
    result = conv.convert(f"# T\n\nIntro.\n\n{block}\n")
    assert block in result


def test_four_backtick_fence_may_contain_three_backticks(conv):
    block = "````\n```\n1. one\n2. two\n```\n````"
    result = conv.convert(f"# T\n\nIntro.\n\n{block}\n")
    assert block in result


def test_prose_around_fence_is_still_converted(conv):
    text = "# T\n\nIntro.\n\n```\n1. a\n2. b\n```\n\n> Note: real\n\n1. First\n2. Second\n"
    result = conv.convert(text)
    assert "<Note>" in result
    assert "<Steps>" in result
    assert "```\n1. a\n2. b\n```" in result


# --- 2. frontmatter merge ---------------------------------------------------


def test_existing_frontmatter_preserved_single_block(conv):
    text = '---\ntitle: "Mine"\nicon: rocket\n---\n\n# Heading\n\nA description paragraph.\n'
    result = conv.convert(text)
    fm, body = split_frontmatter(result)
    assert re.search(r'^title:\s*"?Mine"?\s*$', fm, re.M)
    assert re.search(r'^icon:\s*"?rocket"?\s*$', fm, re.M)
    assert not re.search(r"^---\s*$", body, re.M), "second frontmatter block emitted"
    assert fm.count("title:") == 1


def test_existing_description_wins(conv):
    text = '---\ntitle: "T"\ndescription: "Keep me"\n---\n\nOther first paragraph.\n'
    fm, _ = split_frontmatter(conv.convert(text))
    assert "Keep me" in fm
    assert "Other first paragraph" not in fm


def test_missing_title_and_description_filled(conv):
    text = "---\nicon: bolt\n---\n\n# From Heading\n\nProse paragraph here.\n"
    fm, _ = split_frontmatter(conv.convert(text))
    assert "From Heading" in fm
    assert "Prose paragraph here." in fm
    assert re.search(r"^icon:", fm, re.M)


def test_frontmatter_text_never_leaks_into_description(conv):
    text = '---\ntitle: "Mine"\nicon: x\n---\n\n# Hi\n\nBody\n'
    fm, _ = split_frontmatter(conv.convert(text))
    assert "--- title" not in fm
    assert "icon: x ---" not in fm


# --- 3. idempotence ---------------------------------------------------------

IDEMPOTENCE_INPUTS = {
    "sample_fixture": lambda: (FIXTURES / "sample.mdx").read_text(encoding="utf-8"),
    "empty": lambda: "",
    "heading_only": lambda: "# Title",
    "code_with_steps": lambda: "# T\n\n- a\n  - b\n\n```\n1. one\n2. two\n> Note: x\n```\n\n> Note: real\n",
    "frontmatter": lambda: '---\ntitle: "Mine"\nicon: x\n---\n\n# Hi\n\nBody\n',
    "steps_callouts_cards": lambda: (
        "# T\n\nIntro.\n\n## Getting Started\n\n1. **Sign up** - Create an account\n2. Get a key\n\n"
        "> **Warning:** careful\n\nNeed help?\n\nContact support@example.com\n"
    ),
    "tabs_images": lambda: "# T\n\nJavaScript:\nconst x = 1;\n\nPython:\nx = 1\n\n![Alt](pic.png)\n\n[Guide](guide.md)\n",
    "crlf": lambda: "# T\r\n\r\n> Warning: hi\r\n\r\n1. a\r\n2. b\r\n",
    "unicode": lambda: "# Título ñ 日本語\n\nCafé 😀\n\n> Tip: ünï\n",
}


@pytest.mark.parametrize("name", sorted(IDEMPOTENCE_INPUTS))
def test_idempotent(conv, name):
    once = conv.convert(IDEMPOTENCE_INPUTS[name]())
    twice = MintlifyConverter().convert(once)
    assert twice == once


# --- 4. description rules ---------------------------------------------------


@pytest.mark.parametrize(
    "content,expected",
    [
        ("# Title", ""),
        ("# Title\n", ""),
        ("# Title\n\nFirst prose paragraph.", "First prose paragraph."),
        ("# Title\n\n- a\n- b\n\nReal paragraph.", "Real paragraph."),
        ("# Title\n\n1. a\n2. b\n\nReal paragraph.", "Real paragraph."),
        ("# Title\n\n> Quoted\n\nReal paragraph.", "Real paragraph."),
        ("# Title\n\n```\ncode\n```\n\nReal paragraph.", "Real paragraph."),
        ("# Title\n\n~~~\ncode\n~~~\n\nReal paragraph.", "Real paragraph."),
        ("# Title\n\n<Note>jsx</Note>\n\nReal paragraph.", "Real paragraph."),
        ("# Title\n\n## Sub\n\nReal paragraph.", "Real paragraph."),
        ('---\ntitle: "X"\n---\n\n# X\n\nReal paragraph.', "Real paragraph."),
        ("# Title\n\n- only\n- list", ""),
        ("", ""),
    ],
)
def test_extract_description_rules(conv, content, expected):
    assert conv.extract_description(content) == expected


def test_description_not_a_list_in_frontmatter(conv):
    fm, _ = split_frontmatter(conv.convert("# T\n\n- a\n  - b\n    - c\n"))
    assert 'description: "- a' not in fm


# --- 5. step titles ---------------------------------------------------------


def step_titles(text):
    return re.findall(r'<Step title="([^"]*)"', text)


def test_step_titles_first_second_third(conv):
    out = conv.convert_numbered_steps("1. First step\n2. Second step\n3. Third step")
    assert step_titles(out) == ["First step", "Second step", "Third step"]


def test_step_title_never_bare_step_or_empty(conv):
    out = conv.convert_numbered_steps("1. First step\n2. Step\n3. Next step: Do it")
    for title in step_titles(out):
        assert title.strip().lower() != "step"
        assert title.strip()


def test_step_title_no_raw_bold_markers(conv):
    out = conv.convert_numbered_steps(
        "1. **Authentication** - Secure API key authentication\n2. **Rate limiting** - Fair usage"
    )
    titles = step_titles(out)
    assert len(titles) == 2
    assert all("**" not in t for t in titles)
    assert "Authentication" in titles[0]


@pytest.mark.parametrize(
    "item,expected",
    [
        ("Step 1: Install the CLI", "Install the CLI"),
        ("Next: Configure the app", "Configure the app"),
        ("Then: Run it", "Run it"),
        ("Finally: Deploy", "Deploy"),
    ],
)
def test_step_prefix_stripped_at_separator(conv, item, expected):
    out = conv.convert_numbered_steps(f"1. {item}\n2. Other thing")
    assert step_titles(out)[0].lower() == expected.lower()


@pytest.mark.parametrize("item", ["Firstly set things up", "Stepping stones", "Thenceforth we go"])
def test_step_prefix_only_at_word_boundary(conv, item):
    out = conv.convert_numbered_steps(f"1. {item}\n2. Other thing")
    assert step_titles(out)[0] == item


def test_no_doubled_colon_after_bold_label(conv):
    result = conv.convert(
        "# T\n\n* **Free tier:** 100 requests per hour\n* **Pro tier:** 1,000 requests\n"
    )
    assert ":**:" not in result
    assert "tier::" not in result
    assert "100 requests per hour" in result


# --- 6. link and image ordering --------------------------------------------


def test_md_link_extension_stripped(conv):
    out = conv.convert("# T\n\nSee [Guide](guide.md) and [Other](docs/other.mdx).\n")
    assert not re.search(r"\]\([^)]*\.mdx?\)", out)
    assert "guide" in out and "docs/other" in out


def test_image_path_with_md_in_name_untouched(conv):
    out = conv.convert("# T\n\n![Doc](img/readme.md.png)\n")
    assert "readme.md.png" in out


def convert_with_images(tmp_path, body, names):
    """Convert a page that references real images, with asset handling on."""
    from mintlify_convert.utils import process_directory

    root = tmp_path / "in"
    root.mkdir()
    for name in names:
        (root / name).write_bytes(b"IMG")
    (root / "page.mdx").write_text(f"# T\n\nIntro.\n\n{body}\n", encoding="utf-8")
    out = tmp_path / "out"
    process_directory(root, out, download_assets=True)
    return (out / "page.mdx").read_text(encoding="utf-8")


def test_image_wrapped_in_exactly_one_frame(tmp_path):
    out = convert_with_images(tmp_path, "![Alt text](pic.png)", ["pic.png"])
    assert out.count("<Frame>") == 1
    assert out.count("</Frame>") == 1
    assert out.count("pic.png") == 1


def test_two_images_two_frames_no_rematch(tmp_path):
    out = convert_with_images(tmp_path, "![A](a.png)\n\n![B](b.png)", ["a.png", "b.png"])
    assert out.count("<Frame>") == 2
    assert out.count("a.png") == 1 and out.count("b.png") == 1


def test_missing_alt_gets_default_alt(tmp_path):
    out = convert_with_images(tmp_path, "![](pic.png)", ["pic.png"])
    assert 'alt="' in out and 'alt=""' not in out


# --- 11. callouts and Getting Started --------------------------------------


@pytest.mark.parametrize(
    "src,tag",
    [
        ("> **Warning:** careful", "Warning"),
        ("> **Note:** remember this", "Note"),
        ("> **Tip:** helpful", "Tip"),
        ("> Something neutral here", "Info"),
        ("> Success: it is complete", "Check"),
    ],
)
def test_callout_components(conv, src, tag):
    out = conv.convert_callouts(src)
    assert f"<{tag}>" in out and f"</{tag}>" in out
    assert "<Callout" not in out


def test_multiline_blockquote_is_one_callout(conv):
    out = conv.convert_callouts("> **Note:** line one\n> line two\n")
    assert out.count("<Note>") == 1


def test_getting_started_section_emitted_once(conv):
    text = "# T\n\nIntro text.\n\n## Getting Started\n\n1. Sign up\n2. Get a key\n"
    out = conv.convert(text)
    assert len(re.findall(r"Getting Started", out)) == 1
    assert out.count("<Steps>") == 1


# --- tabs, banner, accordion, cards ----------------------------------------


def test_tabs_generated_for_language_blocks(conv):
    out = conv.convert_tabs("JavaScript:\nconst x = 1;\n\nPython:\nx = 1")
    assert out.count("<Tabs>") == 1 and out.count("</Tabs>") == 1
    assert '<Tab title="JavaScript">' in out
    assert '<Tab title="Python">' in out
    assert "const x = 1;" in out and "x = 1" in out


def test_tabs_nested_correctly(conv):
    out = conv.convert_tabs("JavaScript:\nconst x = 1;\n\nPython:\nx = 1")
    assert out.index("<Tabs>") < out.index("<Tab ") < out.index("</Tab>") < out.index("</Tabs>")
    assert out.count("<Tab ") == out.count("</Tab>") == 2


def test_single_language_label_is_not_tabs(conv):
    out = conv.convert_tabs("Python:\nx = 1")
    assert "<Tabs>" not in out


@pytest.mark.parametrize("label,kind", [("Deprecated", "warning"), ("Notice", "info")])
def test_banner(conv, label, kind):
    out = conv.convert_banner(f"{label}: This API is changing soon.\n\nBody text.")
    assert f'<Banner type="{kind}">' in out
    assert "</Banner>" in out
    assert "Body text." in out


def test_accordion_for_advanced_section(conv):
    out = conv.convert("# T\n\nIntro.\n\n### Advanced Section\nDeep details.\n")
    assert '<Accordion title="Advanced Section">' in out
    assert "</Accordion>" in out


def test_help_card(conv):
    out = conv.convert_help_sections("Need help?\n\nContact support@example.com")
    assert '<Card title="Need help?"' in out and "</Card>" in out


# --- 12. --validate false positives ----------------------------------------


def test_validate_ignores_jsx_in_fenced_code(conv):
    assert conv.validate_mdx("# T\n\n```\n<Note>unclosed in code\n```\n") == []
    assert conv.validate_mdx("# T\n\n~~~\n<Steps>\n~~~\n") == []


def test_validate_still_flags_real_unclosed_tag(conv):
    errors = conv.validate_mdx("<Note>real problem\n\n```\n<Tip>\n```\n")
    assert errors and "Note" in errors[0]


def test_convert_validate_flag_no_errors_for_code_jsx(conv):
    conv.convert("# T\n\nIntro.\n\n```jsx\n<Note>\n```\n", validate=True)
    assert conv.validation_errors == []


# --- misc robustness --------------------------------------------------------


def test_empty_string_yields_valid_minimal_output(conv):
    out = conv.convert("")
    fm, _ = split_frontmatter(out)
    assert "title:" in fm


def test_crlf_input_converts_components(conv):
    out = conv.convert("# T\r\n\r\n> Warning: hi\r\n\r\n1. a\r\n2. b\r\n")
    assert "<Warning>" in out and "<Steps>" in out


def test_unicode_preserved(conv):
    out = conv.convert("# Título ñ 日本語\n\nCafé 😀\n")
    assert "Título ñ 日本語" in out and "😀" not in out  # text stays, emoji become icons


def test_image_framed_even_when_assets_not_copied(conv):
    out = conv.convert("# T\n\nIntro.\n\n![A](pic.png)\n")
    assert out.count("<Frame>") == 1
    assert out.count("pic.png") == 1


def test_img_already_in_frame_left_alone(conv):
    src = '# T\n\nIntro.\n\n<Frame>\n  <img src="pic.png" alt="A" />\n</Frame>\n'
    out = conv.convert(src)
    assert out.count("<Frame>") == 1
    assert out.count("<img") == 1
