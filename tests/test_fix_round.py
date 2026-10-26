"""Regression tests for the fix round (converter items 1-9)."""

import os
import re
import time

import pytest

from mintlify_convert.converter import MAX_INPUT_BYTES, MintlifyConverter
from mintlify_convert.utils import process_directory

from .conftest import run_python


@pytest.fixture
def conv():
    return MintlifyConverter()


def count(text, needle):
    return len(re.findall(needle, text))


# --- 1. tabs: linear scan, no pair splitting, label never a description -----


def test_20000_tab_labels_finish_quickly():
    code = (
        "import time\n"
        "from mintlify_convert.converter import MintlifyConverter\n"
        "t = time.perf_counter()\n"
        "MintlifyConverter().convert_tabs('Python:\\n' * 20000)\n"
        "print(time.perf_counter() - t)\n"
    )
    result = run_python(code, timeout=60)
    assert result.returncode == 0, result.stderr[-500:]
    # Linear is ~tens of ms; quadratic is minutes. Generous bound for slow runners.
    assert float(result.stdout.strip()) < 10


def test_four_language_labels_make_one_tab_group(conv):
    src = "JavaScript:\na = 1\n\nPython:\nb = 2\n\nGo:\nc := 3\n\nRuby:\nd = 4"
    out = conv.convert_tabs(src)
    assert out.count("<Tabs>") == 1 and out.count("</Tabs>") == 1
    assert count(out, r"<Tab title=") == 4


def test_separate_tab_groups_stay_separate(conv):
    src = (
        "JavaScript:\na = 1\n\nPython:\nb = 2\n\nSome prose in between.\n\n"
        "Go:\nc := 3\n\nRuby:\nd = 4"
    )
    out = conv.convert_tabs(src)
    assert out.count("<Tabs>") == 2
    assert count(out, r"<Tab title=") == 4


def test_lone_label_lines_are_not_swallowed(conv):
    src = "Python:\nx = 1\n\nProse after.\n\nGo:\ny := 2\n"
    out = conv.convert_tabs(src)
    assert "<Tabs>" not in out
    assert "Prose after." in out and "x = 1" in out and "y := 2" in out


def test_tab_label_never_used_as_description(conv):
    src = "# T\n\nJavaScript:\nconst x = 1;\n\nPython:\nx = 1\n"
    assert not conv.extract_description(src).startswith("JavaScript:")
    fm = conv.convert(src).split("\n---", 1)[0]
    assert 'description: "JavaScript:' not in fm


# --- 2. cheap pre-checks near the 1 MiB cap ---------------------------------

NEAR_CAP = {
    "brackets": f"'[' * ({MAX_INPUT_BYTES} - 16)",
    "img_open": f"'<img ' * ({MAX_INPUT_BYTES} // 5 - 4)",
    "link_open": f"'[a](' * ({MAX_INPUT_BYTES} // 4 - 4)",
}


@pytest.mark.parametrize("name", sorted(NEAR_CAP))
def test_near_cap_input_finishes_in_time(name):
    code = (
        "from mintlify_convert.converter import MintlifyConverter\n"
        f"MintlifyConverter().convert({NEAR_CAP[name]})\n"
    )
    result = run_python(code, timeout=60)
    assert result.returncode == 0, result.stderr[-500:]


# --- 3. numbered lists: one <Steps> per list --------------------------------


def test_loose_list_is_one_steps_block(conv):
    out = conv.convert_numbered_steps("1. Alpha\n\n2. Beta\n\n3. Gamma")
    assert out.count("<Steps>") == 1
    assert count(out, r"<Step title=") == 3


def test_fence_between_steps_stays_in_one_steps_block(conv):
    src = "1. Install it\n\n```bash\nnpm install foo\n```\n\n2. Run it\n\n```bash\nfoo run\n```\n"
    out = conv.convert_numbered_steps(src)
    assert out.count("<Steps>") == 1
    assert count(out, r"<Step title=") == 2
    assert "```bash\nnpm install foo\n```" in out
    # the first fence belongs to step 1: it appears before the second <Step
    second = [m.start() for m in re.finditer(r"<Step title=", out)][1]
    assert out.index("npm install foo") < second
    assert out.index("foo run") > second


def test_indented_continuation_stays_in_step(conv):
    out = conv.convert_numbered_steps("1. First thing\n   extra detail line\n2. Second thing")
    assert out.count("<Steps>") == 1
    assert "extra detail line" in out
    assert count(out, r"<Step title=") == 2


def test_prose_line_ends_the_list(conv):
    src = "1. a\n2. b\n\nA prose paragraph.\n\n1. c\n2. d\n"
    out = conv.convert_numbered_steps(src)
    assert out.count("<Steps>") == 2
    assert out.index("A prose paragraph.") > out.index("</Steps>")


def test_loose_list_via_full_convert_idempotent(conv):
    src = "# T\n\nIntro.\n\n1. Install\n\n```bash\nnpm i\n```\n\n2. Run\n"
    once = conv.convert(src)
    assert once.count("<Steps>") == 1
    assert MintlifyConverter().convert(once) == once


# --- 4. step titles ---------------------------------------------------------

LONG = (
    "Configure the `config.yaml` file with your **API key**, the region you operate in, "
    "and every optional setting that applies to the deployment"
)


def titles(text):
    return re.findall(r'<Step title="([^"]*)"', text)


def test_step_title_plain_text(conv):
    out = conv.convert_numbered_steps(f"1. {LONG}\n2. Done")
    title = titles(out)[0]
    assert "`" not in title and "**" not in title
    assert "config.yaml" in title or "Configure" in title


def test_step_title_not_cut_mid_word_and_no_ellipsis(conv):
    out = conv.convert_numbered_steps(f"1. {LONG}\n2. Done")
    title = titles(out)[0]
    assert not title.endswith("...") and "…" not in title
    assert len(title) <= 100
    plain_words = set(re.sub(r"[`*]", "", LONG).replace(",", "").split())
    assert all(w.strip(",.") in plain_words for w in title.split())


def test_step_body_keeps_full_text(conv):
    out = conv.convert_numbered_steps(f"1. {LONG}\n2. Done")
    assert "every optional setting that applies to the deployment" in out


@pytest.mark.parametrize(
    "item", ["Run `npm install`", "**Bold** start of step", "Use `a` and `b` together"]
)
def test_step_title_strips_inline_markup(conv, item):
    title = titles(conv.convert_numbered_steps(f"1. {item}\n2. Other"))[0]
    assert "`" not in title and "**" not in title
    assert title.strip()


def test_step_title_attribute_safe_for_quotes(conv):
    out = conv.convert_numbered_steps('1. Say "hello" to the API\n2. Other')
    assert len(re.findall(r"<Step title=", out)) == 2
    assert re.search(r'<Step title="[^"]*"[^">]*>', out)


# --- 5. accordions are keyword-restricted -----------------------------------


@pytest.mark.parametrize(
    "heading",
    ["Options", "Input Pattern", "Supported Types", "From Source", "Basic Usage", "Installation"],
)
@pytest.mark.parametrize("level", ["##", "###"])
def test_ordinary_headings_are_not_accordions(conv, heading, level):
    src = f"# T\n\nIntro.\n\n{level} {heading}\n\nSome reference text.\n"
    out = conv.convert(src)
    assert "<Accordion" not in out
    assert f"{level} {heading}" in out


@pytest.mark.parametrize("heading", ["FAQ", "Troubleshooting", "Advanced Configuration"])
def test_faq_style_headings_are_accordions(conv, heading):
    out = conv.convert(f"# T\n\nIntro.\n\n### {heading}\n\nDetails here.\n")
    assert f'<Accordion title="{heading}">' in out
    assert "</Accordion>" in out


@pytest.mark.parametrize("next_heading", ["## Next Section", "### Sibling", "#### Deeper"])
def test_accordion_ends_at_next_heading_of_any_level(conv, next_heading):
    src = f"# T\n\nIntro.\n\n### FAQ\n\nAnswer text.\n\n{next_heading}\n\nOutside text.\n"
    out = conv.convert(src)
    assert out.index("Answer text.") < out.index("</Accordion>") < out.index(next_heading)
    assert out.index("</Accordion>") < out.index("Outside text.")
    assert out.count("<Accordion") == out.count("</Accordion>") == 1


def test_accordion_conversion_is_idempotent(conv):
    once = conv.convert("# T\n\nIntro.\n\n### FAQ\n\nAnswer.\n\n## Options\n\nText.\n")
    assert MintlifyConverter().convert(once) == once


# --- 6. relative links outside the input root -------------------------------


def test_link_outside_input_root_unchanged(tmp_path):
    root = tmp_path / "in"
    root.mkdir()
    (root / "page.mdx").write_text(
        "# P\n\nIntro.\n\nSee [examples](../examples/) and [more](../examples/readme.md).\n"
    )
    out = tmp_path / "out"
    process_directory(root, out)
    text = (out / "page.mdx").read_text()
    assert "(../examples/)" in text
    assert "(../examples/readme.md)" in text


def test_link_inside_root_still_rewritten(tmp_path):
    root = tmp_path / "in"
    (root / "sub").mkdir(parents=True)
    (root / "other.mdx").write_text("# O\n\nBody.\n")
    (root / "sub" / "page.mdx").write_text("# P\n\nIntro.\n\nSee [other](../other.md).\n")
    out = tmp_path / "out"
    process_directory(root, out)
    text = (out / "sub" / "page.mdx").read_text()
    assert ".md)" not in text
    assert "other" in text


# --- 7. warnings for skipped sources, exit code stays 0 ---------------------


def test_file_source_skip_warns_on_stderr_exit_0(tmp_path, run_cli):
    d = tmp_path / "in"
    d.mkdir()
    (d / "p.mdx").write_text("# P\n\nIntro.\n\n![x](file:///etc/passwd)\n")
    code, out, err = run_cli(d, "-o", tmp_path / "out", "--download-assets")
    assert code == 0
    assert "file:" in err
    assert [p for p in (tmp_path / "out").rglob("*") if p.is_file() and p.suffix != ".mdx"] == []


def test_symlinked_input_file_skip_warns_on_stderr_exit_0(tmp_path, run_cli):
    d = tmp_path / "in"
    d.mkdir()
    (d / "real.mdx").write_text("# Real\n\nBody.\n")
    secret = tmp_path / "secret.mdx"
    secret.write_text("# S\n\nSECRET\n")
    try:
        os.symlink(secret, d / "link.mdx")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    code, out, err = run_cli(d, "-o", tmp_path / "out")
    assert code == 0
    assert "link.mdx" in err
    assert not (tmp_path / "out" / "link.mdx").exists()


# --- 8. --validate masking matches the converter ----------------------------


@pytest.mark.parametrize(
    "text",
    [
        "# T\n\nIntro.\n\n```js\nconst a = `x`;\n<Note>\n\nUse `foo` here.\n",
        "# T\n\nIntro.\n\n~~~\n<Note>\nUse `foo` and `bar`.\n",
        "# T\n\nIntro with `inline` code.\n\n```\n<Steps>\n```\n\nMore `code`.\n",
    ],
)
def test_validate_no_false_unclosed_tags(conv, text):
    conv.convert(text, validate=True)
    assert not [e for e in conv.validation_errors if "Unclosed" in e], conv.validation_errors


def test_validate_real_unclosed_tag_still_reported(conv):
    conv.convert("# T\n\n<Note>never closed\n\nUse `foo`.\n", validate=True)
    assert any("Unclosed" in e and "Note" in e for e in conv.validation_errors)


def test_validate_inline_backticks_hide_tags(conv):
    assert conv.validate_mdx("Use the `<Note>` tag, it is `<Tip>` too.\n") == []


# --- converter design choices ------------------------------------------------


@pytest.mark.parametrize(
    "method,src",
    [
        ("convert_callouts", "> ```js\n> x\n> ```\n"),
        ("convert_banner", "Deprecated: ```js\nx\n```\n"),
        ("convert_numbered_steps", "1. ```js\nx\n```\n2. b\n"),
    ],
)
def test_construct_starting_with_code_fence_left_unconverted(conv, method, src):
    assert getattr(conv, method)(src) == src


def test_banner_only_matches_at_paragraph_start(conv):
    mid = "Some text Deprecated: gone soon.\n"
    assert conv.convert_banner(mid) == mid
    assert '<Banner type="warning">' in conv.convert_banner("Deprecated: gone soon.\n\nBody\n")
    assert '<Banner type="warning">' in conv.convert_banner("Para.\n\nDeprecated: gone soon.\n")


def test_help_card_only_matches_at_paragraph_start(conv):
    mid = "Intro line Need help?\n\nContact x\n"
    assert conv.convert_help_sections(mid) == mid
    assert "<Card" in conv.convert_help_sections("Para.\n\nNeed help?\n\nContact x\n")


@pytest.mark.parametrize(
    "terminator", ["## Head", "> quoted", "<Note>x</Note>", "| h | i |\n|---|---|"]
)
def test_heading_quote_tag_or_table_ends_a_step(conv, terminator):
    out = conv.convert_numbered_steps(f"1. a\n2. b\n{terminator}\n")
    assert out.count("<Steps>") == 1
    assert out.index("</Steps>") < out.index(terminator.splitlines()[0])
    assert out.count("<Step title=") == 2


def test_lazy_continuation_stays_in_step(conv):
    out = conv.convert_numbered_steps("1. a\nlazy text\n2. b\n")
    assert out.count("<Steps>") == 1
    assert out.index("lazy text") < out.index("</Step>")


# --- fix round 2: reviewer findings -----------------------------------------

FENCE_LINE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def assert_balanced_fences(text):
    """Every opened fence closes, and no fence opener sits inside another fence's body."""
    open_fence = None
    for number, line in enumerate(text.split("\n"), 1):
        match = FENCE_LINE.match(line)
        if open_fence is None:
            if match:
                open_fence = (match.group(1)[0], len(match.group(1)))
            continue
        if not match:
            continue
        char, length = open_fence
        marker, rest = match.group(1), match.group(2)
        if marker[0] == char and len(marker) >= length and not rest.strip():
            open_fence = None
        elif marker[0] == char:
            raise AssertionError(f"fence opener nested inside a fence at line {number}: {line!r}")
    assert open_fence is None, f"unclosed fence in output:\n{text}"


def assert_idempotent(src):
    once = MintlifyConverter().convert(src)
    twice = MintlifyConverter().convert(once)
    assert twice == once, f"not idempotent for {src!r}"
    return once


def test_tab_block_with_prose_before_fence_is_valid_and_idempotent():
    src = "Python:\nInstall first:\n```bash\npip install x\n```\nBash:\necho hi\n"
    for out in (
        MintlifyConverter().convert_tabs(src),
        assert_idempotent("# T\n\n" + src),
    ):
        assert_balanced_fences(out)
        assert "pip install x" in out and "echo hi" in out


@pytest.mark.parametrize("src", ["# T\nhello\n", "# T\n`a`\n", "# T\n[\n", "# T\nSupport\n"])
def test_heading_directly_followed_by_prose_is_idempotent(src):
    assert_idempotent(src)


def test_duplicate_h1_is_idempotent():
    assert_idempotent("# Title\n# Title\n")


FRAGMENTS = [
    "# Title",
    "Intro paragraph.",
    "Python:\nInstall first:\n```bash\npip install x\n```\nBash:\necho hi",
    "JavaScript:\nconst a = 1;\n\nPython:\na = 1",
    "```js\nconst a = `x`;\n```",
    "~~~\n1. in fence\n> quote in fence\n~~~",
    "1. One\n2. Two",
    "1. Install\n\n```bash\nnpm i\n```\n\n2. Run",
    "> **Note:** a note",
    "> ```js\n> x\n> ```",
    "Deprecated: going away.",
    "Need help?\n\nContact us",
    "### FAQ\n\nAnswer.",
    "### Options\n\nText.",
    "## Getting Started\n\nBegin.",
    "- **Free tier:** 100 requests",
    "[Guide](guide.md) and `inline` code",
    "![Alt](pic.png)",
    "`a`",
    "[",
    "Support",
    "| h | i |\n|---|---|\n| 1 | 2 |",
    "<Note>\nalready converted\n</Note>",
]
UNCLOSED = ["```js\nconst a = 1;", "~~~\n<Note>\nUse `foo`."]


def random_documents(seed, count, pool, max_parts=4):
    import random

    rng = random.Random(seed)
    for _ in range(count):
        parts = [rng.choice(pool) for _ in range(rng.randint(1, max_parts))]
        yield "".join(p + rng.choice(["\n", "\n\n", "\n\n\n"]) for p in parts)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_random_fragment_combinations_idempotent_with_balanced_fences(seed):
    for doc in random_documents(seed, 150, FRAGMENTS):
        assert_balanced_fences(assert_idempotent(doc))


def test_random_combinations_with_unclosed_fence_idempotent():
    for doc in random_documents(7, 100, FRAGMENTS + UNCLOSED):
        assert_idempotent(doc)


def test_tab_with_prose_and_fence_is_unwrapped_and_other_tab_fenced():
    src = "Python:\nInstall first:\n```bash\npip install x\n```\nBash:\necho hi\n"
    out = MintlifyConverter().convert_tabs(src)
    assert "Install first:\n```bash\npip install x\n```" in out
    assert "```python" not in out
    assert "```bash\necho hi\n```" in out


@pytest.mark.parametrize(
    "src,expected",
    [
        ("# T\nhello\n", "hello"),
        ("# T\n`a`\n", "a"),
        ("# T\n[\n", "["),
        ("# T\nSupport\n", "Support"),
        ("# T\n## Sub\ntext\n", "text"),
    ],
)
def test_prose_directly_under_heading_is_the_description(src, expected):
    assert MintlifyConverter().extract_description(src) == expected


def test_duplicate_leading_h1_removed_leaving_empty_body():
    out = assert_idempotent("# Title\n# Title\n")
    assert out.count("# Title") == 0
    assert out.rstrip().endswith("---")


def test_duplicate_h1_with_frontmatter_title_all_removed():
    out = assert_idempotent('---\ntitle: "T"\n---\n\n# T\n# T\n\nBody.\n')
    assert "# T" not in out and "Body." in out


def test_non_leading_duplicate_h1_is_stable():
    out = assert_idempotent("x\n\n# T\n# T\n")
    assert out.count("# T") == 1


# --- fix round 3: repeated lines must not be quadratic ----------------------


def best_time(fn, repeats=3):
    best = float("inf")
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return best


def assert_linear(make_call, n=20000, factor=4, limit_ratio=8, epsilon=0.02):
    """t(factor*n) must stay under limit_ratio*t(n): linear is ~4x, quadratic ~16x."""
    small = best_time(make_call(n))
    large = best_time(make_call(n * factor))
    assert large < limit_ratio * small + epsilon, f"n={n}: {small:.4f}s, {factor}n: {large:.4f}s"


def description_call(unit):
    def make(n):
        text = unit * n
        return lambda: MintlifyConverter().extract_description(text)

    return make


# Large enough that a per-heading re-slice (ratio ~14 here, ~8 at 20,000) clearly exceeds the bound.
TITLE_N = 40000


def title_call(unit, body_prefix="", expected_title=None):
    def make(n):
        text = body_prefix + unit * n
        return lambda: MintlifyConverter().remove_original_title(text, expected_title)

    return make


@pytest.mark.parametrize("unit", ["## h\n", "# h\n", "### h\n"])
def test_extract_description_one_block_of_many_headings_is_linear(unit):
    # One block of consecutive heading lines: the shape a list.pop(0) loop made quadratic.
    assert_linear(description_call(unit))


def test_extract_description_many_heading_only_blocks_is_linear():
    assert_linear(description_call("## h\n\n"))


def test_remove_original_title_many_duplicate_h1_without_frontmatter_title_is_linear():
    assert_linear(title_call("# T\n"), n=TITLE_N)


def test_remove_original_title_many_duplicate_h1_with_frontmatter_title_is_linear():
    assert_linear(title_call("# T\n", expected_title="T"), n=TITLE_N)


def test_remove_original_title_duplicate_h1_separated_by_blank_lines_is_linear():
    assert_linear(title_call("# T\n\n\n", expected_title="T"), n=TITLE_N)


def test_many_duplicate_h1_still_all_removed():
    # Guard the behavior while the algorithm is optimised.
    out = MintlifyConverter().remove_original_title("# T\n" * 50 + "Body\n", "T")
    assert out == "Body\n"


# Real cost is 1-2 s (about 5 s for fences); limits are roughly 3x the measured cost per shape.
REPEATED_LINE_SHAPES = {
    "h1": ("# a\n", 4),
    "h2": ("## a\n", 6),
    "heading_with_text": ("# a\ntext\n", 6),
    "list_item": ("- a\n", 6),
    "quote": ("> a\n", 6),
    "tag": ("<Note>\n", 5),
    "tab_label": ("Python:\n", 4),
    "fence": ("```\n", 15),
    "inline_code": ("`a`\n", 15),
}


@pytest.mark.parametrize("name", sorted(REPEATED_LINE_SHAPES))
def test_repeated_line_near_cap_with_validate_finishes_in_time(name):
    unit, limit = REPEATED_LINE_SHAPES[name]
    code = (
        "from mintlify_convert.converter import MintlifyConverter, MAX_INPUT_BYTES\n"
        f"unit = {unit!r}\n"
        "text = unit * ((MAX_INPUT_BYTES - 64) // len(unit))\n"
        "MintlifyConverter().convert(text, validate=True)\n"
    )
    result = run_python(code, timeout=limit)
    assert result.returncode == 0, result.stderr[-500:]
