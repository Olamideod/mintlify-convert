"""Image-copy security, input/output path safety and regex time bounds."""

import os

import pytest

from mintlify_convert.converter import MAX_INPUT_BYTES, MintlifyConverter
from mintlify_convert.utils import process_directory, process_file

from .conftest import run_python


@pytest.fixture
def tree(tmp_path):
    """tmp/in (input root), tmp/out (output), tmp/secret.png outside the root."""
    root = tmp_path / "in"
    root.mkdir()
    (tmp_path / "secret.png").write_bytes(b"SECRET")
    return tmp_path, root, tmp_path / "out"


def copied_files(out):
    return [p for p in out.rglob("*") if p.is_file() and p.suffix != ".mdx"]


def convert_page(root, out, body, **kw):
    (root / "page.mdx").write_text(f"# Page\n\nIntro.\n\n{body}\n", encoding="utf-8")
    process_directory(root, out, **kw)
    page = out / "page.mdx"
    assert page.exists(), "page was not converted at all (test would be vacuous)"
    return page.read_text(encoding="utf-8")


def test_image_copied_when_enabled(tree):
    _, root, out = tree
    (root / "pic.png").write_bytes(b"PNG")
    text = convert_page(root, out, "![A](pic.png)", download_assets=True)
    assert (out / "images" / "pic.png").read_bytes() == b"PNG"
    assert "/images/pic.png" in text


def test_image_not_copied_when_disabled(tree):
    _, root, out = tree
    (root / "pic.png").write_bytes(b"PNG")
    convert_page(root, out, "![A](pic.png)")
    assert copied_files(out) == []


def test_destination_uses_basename_only(tree):
    _, root, out = tree
    (root / "a" / "b").mkdir(parents=True)
    (root / "a" / "b" / "deep.png").write_bytes(b"PNG")
    (root / "a" / "page.mdx").write_text("# P\n\nIntro.\n\n![x](b/deep.png)\n")
    process_directory(root, out, download_assets=True)
    assert (out / "images" / "deep.png").is_file()
    assert not (out / "images" / "b").exists()


def test_parent_traversal_rejected(tree):
    tmp, root, out = tree
    convert_page(root, out, "![x](../secret.png)", download_assets=True)
    assert not [p for p in out.rglob("secret.png")]


def test_deep_traversal_rejected(tree):
    tmp, root, out = tree
    convert_page(root, out, "![x](a/../../secret.png)", download_assets=True)
    assert not [p for p in out.rglob("secret.png")]


def test_absolute_path_rejected(tree):
    tmp, root, out = tree
    convert_page(root, out, f"![x]({tmp / 'secret.png'})", download_assets=True)
    assert not [p for p in out.rglob("secret.png")]


def test_symlink_image_not_copied(tree):
    tmp, root, out = tree
    try:
        os.symlink(tmp / "secret.png", root / "link.png")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    convert_page(root, out, "![x](link.png)", download_assets=True)
    assert not (out / "images" / "link.png").exists()
    assert b"SECRET" not in b"".join(p.read_bytes() for p in out.rglob("*") if p.is_file())


@pytest.mark.parametrize(
    "src",
    [
        "file:///etc/passwd",
        "file:secret.png",
        "data:image/png;base64,AAAA",
        "//evil.example/x.png",
        "https://example.com/x.png",
    ],
)
def test_non_local_sources_not_copied(tree, src):
    _, root, out = tree
    convert_page(root, out, f"![x]({src})", download_assets=True)
    assert copied_files(out) == []


@pytest.mark.parametrize("name", ["notes.txt", "run.py", "id_rsa", "config.env", "payload.sh"])
def test_extension_allow_list(tree, name):
    _, root, out = tree
    (root / name).write_text("not an image")
    convert_page(root, out, f"![x]({name})", download_assets=True)
    assert copied_files(out) == []


@pytest.mark.parametrize("name", ["a.png", "b.jpg", "c.jpeg", "d.gif"])
def test_common_image_extensions_allowed(tree, name):
    _, root, out = tree
    (root / name).write_bytes(b"IMG")
    convert_page(root, out, f"![x]({name})", download_assets=True)
    assert (out / "images" / name).is_file()


def test_handle_images_without_source_file_does_not_crash():
    out = MintlifyConverter().handle_images("![A](pic.png)")
    assert "pic.png" in out


# --- 8. regex bounds -------------------------------------------------------

PATHOLOGICAL = {
    "open_brackets": "'[' * 20000",
    "long_alt": "'![' + 'a' * 50000",
    "long_target": "'[a](' + 'b' * 50000",
    "long_image_target": "'![a](' + 'b' * 50000",
    "repeated_links": "'[a](' * 20000",
    "nested_parens": "'[a](' + '(' * 20000",
    "many_bangs": "'![a' * 20000",
    "many_img_tags": "'<img ' * 20000",
    "unclosed_fence": "'```\\n' + '1. a\\n' * 10000",
    "many_numbered": "'1. item\\n' * 20000",
    "many_quotes": "'> q\\n' * 20000",
    "many_headings": "'### h\\nline\\n' * 10000",
    "tab_labels": "'Python:\\n' * 20000",
    "alternating_tab_labels": "'JavaScript:\\nx\\nPython:\\ny\\n' * 5000",
}

# Generous: a quadratic/exponential regression runs for minutes, a slow CI runner only seconds.
TIME_LIMIT = 30


@pytest.mark.parametrize("name", sorted(PATHOLOGICAL))
def test_pathological_input_finishes_in_time(name):
    code = (
        "from mintlify_convert.converter import MAX_INPUT_BYTES, MintlifyConverter\n"
        f"text = {PATHOLOGICAL[name]}\n"
        "MintlifyConverter().convert(text)\n"
    )
    result = run_python(code, timeout=TIME_LIMIT)
    assert result.returncode == 0, result.stderr[-500:]


def test_input_over_cap_rejected_by_process_file(tmp_path, capsys):
    big = tmp_path / "big.mdx"
    big.write_bytes(b"a" * (MAX_INPUT_BYTES + 1))
    ok, _ = process_file(big, tmp_path / "out.mdx")
    captured = capsys.readouterr()
    assert not ok
    assert not (tmp_path / "out.mdx").exists()
    assert any(w in (captured.out + captured.err).lower() for w in ("large", "size", "limit"))


def test_input_over_cap_rejected_by_convert():
    with pytest.raises(ValueError, match="(?i)large|size|limit"):
        MintlifyConverter().convert("a" * (MAX_INPUT_BYTES + 1))


# --- 9. output path safety -------------------------------------------------


def test_input_equals_output_refused(tmp_path, run_cli):
    f = tmp_path / "doc.mdx"
    f.write_text("# T\n\nBody.\n")
    code, out, err = run_cli(f, "-o", f)
    assert code != 0
    assert f.read_text() == "# T\n\nBody.\n"
    assert err.strip()


def test_directory_output_equals_input_refused(tmp_path, run_cli):
    d = tmp_path / "docs"
    d.mkdir()
    (d / "a.mdx").write_text("# A\n\nBody.\n")
    code, out, err = run_cli(d, "-o", d)
    assert code != 0
    assert (d / "a.mdx").read_text() == "# A\n\nBody.\n"


def test_output_nested_in_input_refused(tmp_path, run_cli):
    d = tmp_path / "docs"
    d.mkdir()
    (d / "a.mdx").write_text("# A\n\nBody.\n")
    code, out, err = run_cli(d, "-o", d / "converted")
    assert code != 0
    assert not (d / "converted").exists()


def test_input_nested_in_output_refused(tmp_path, run_cli):
    outer = tmp_path / "outer"
    d = outer / "docs"
    d.mkdir(parents=True)
    (d / "a.mdx").write_text("# A\n\nBody.\n")
    code, out, err = run_cli(d, "-o", outer)
    assert code != 0
    assert [p.name for p in outer.iterdir()] == ["docs"]


def test_symlinked_input_file_skipped(tmp_path):
    root = tmp_path / "in"
    root.mkdir()
    (root / "real.mdx").write_text("# Real\n\nBody.\n")
    secret = tmp_path / "secret.mdx"
    secret.write_text("# Secret\n\nTOP-SECRET-CONTENT\n")
    try:
        os.symlink(secret, root / "link.mdx")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    out = tmp_path / "out"
    meta = process_directory(root, out)
    assert (out / "real.mdx").exists()
    assert not (out / "link.mdx").exists()
    assert "TOP-SECRET-CONTENT" not in "".join(p.read_text() for p in out.rglob("*.mdx"))
    assert len(meta) == 1


# --- 10. empty input -------------------------------------------------------


@pytest.mark.parametrize("content", ["", "   \n\n"])
def test_empty_input_warns_and_writes_valid_output(tmp_path, capsys, content):
    src = tmp_path / "empty.mdx"
    src.write_text(content)
    dst = tmp_path / "out.mdx"
    ok, _ = process_file(src, dst)
    captured = capsys.readouterr()
    assert ok
    assert dst.read_text().startswith("---\n")
    assert "empty" in (captured.out + captured.err).lower()
