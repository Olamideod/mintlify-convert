#!/usr/bin/env python3
"""
MDX to Mintlify format converter.

Converts plain MDX/Markdown into Mintlify components (Steps, Callouts, Cards,
Accordions, Tabs, Banners, Frames) while leaving fenced code untouched, merging
existing frontmatter and producing output that converts to itself.
"""

import json
import os
import posixpath
import re
import shutil
from pathlib import Path
from urllib.parse import unquote
from typing import Dict, Iterator, List, Optional, Tuple

from . import docusaurus
from .icons import convert_emoji_line, resolve_icon, strip_emoji, strip_emoji_everywhere

# Inputs larger than this are rejected before any regex work (1 MiB).
MAX_INPUT_BYTES = 1024 * 1024

IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"})

# Placeholders for masked code. Private-use characters keep them out of prose.
_TOKEN_OPEN = ""
_TOKEN_CLOSE = ""
_TOKEN_RE = re.compile(_TOKEN_OPEN + r"([FC])(\d+)" + _TOKEN_CLOSE)
_FENCE_OPEN_RE = re.compile(r"^([ \t]*)(`{3,}|~{3,})(.*)$")
_INLINE_CODE_RE = re.compile(r"(?<!`)(`+)(?!`)([^\n]{1,500}?)(?<!`)\1(?!`)")

_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
_HEADING_RE = re.compile(r"^#{1,6}(?:[ \t]|$)")
_H1_RE = re.compile(r"^#[ \t]+(.+?)[ \t]*$", re.MULTILINE)
_NON_PROSE_RE = re.compile(
    r"^\s*(?:#{1,6}(?:\s|$)|[-*+]\s|\d+[.)]\s|>|<|\||import\s|export\s|\[[^\]\n]+\]:\s|\*\*[^*\n]+\*\*\s*$|"
    r"-{3,}\s*$|\*{3,}\s*$|_{3,}\s*$|:::|!\[|\[\^|" + _TOKEN_OPEN + r"F)"
)
_STEP_PREFIX_RE = re.compile(
    r"^(?:(?:First|Next|Then|Finally)\b|Step\s+\d+\b)[ \t]*[:,.\-–—][ \t]*",
    re.IGNORECASE,
)
# Lines a prose block (banner or help card text) must not run into: a JSX/HTML tag, a
# heading or a masked code block.
_TAG_LINE = r"[ \t]*(?:</?[A-Za-z]|#{1,6}\s|" + _TOKEN_OPEN + "F)"
# Component tags that tab content must stop at (unfenced JSX in tab code is still allowed).
_COMPONENT_LINE_RE = re.compile(
    r"^\s*</?(?:Steps?|Tabs?|Cards?|Accordion|Frame|Banner|Warning|Note|Tip|Info|Check)\b"
)
_BLOCK_START_RE = re.compile(r"#{1,6}(?:\s|$)|>|<|\||-{3,}\s*$|\*{3,}\s*$|_{3,}\s*$")
_NUMBERED_RE = re.compile(r"^[ \t]*(\d{1,9})\.[ \t]+(\S.*)$")


class _NumberedItem:
    """Numbered list item matcher; an item that opens with a code fence is not a step.

    "1. ```js" would turn into an indented fence opener inside the Step on output and change
    how the page masks code on a second conversion.
    """

    @staticmethod
    def match(line: str):
        m = _NUMBERED_RE.match(line)
        if m and _FENCE_OPEN_RE.match(m.group(2)):
            return None
        return m


_VOID_TAGS = frozenset(
    {
        "br",
        "hr",
        "img",
        "input",
        "meta",
        "link",
        "source",
        "area",
        "base",
        "col",
        "embed",
        "wbr",
        "track",
        "param",
    }
)
_LANGS = (
    r"JavaScript|Python|TypeScript|Ruby|Go|Java|PHP|Curl|Node\.js|React|"
    r"Vue|Angular|Bash|Shell|PowerShell"
)
_TAB_LABEL_RE = re.compile(rf"^({_LANGS}):\s*$", re.IGNORECASE)


# --- bounded link and image scanners ---------------------------------------
# These replace the equivalent regexes: a regex retries every "[" and rescans up to
# 2,500 characters each time, which is quadratic on adversarial input. Anchoring on
# "](" with str.find keeps every step bounded and fast.

_TEXT_MAX = 500
_TARGET_MAX = 2000
_IMG_ATTRS_MAX = 2000


def _target_end(text: str, start: int) -> int:
    """Index of the ')' that closes a link target starting at `start`; parentheses inside the
    target (wiki/page_(1).md) are allowed when balanced. -1 when there is none."""
    limit = min(len(text), start + _TARGET_MAX + 1)
    first = text.find(")", start, limit)
    if first == -1:
        return -1
    newline = text.find("\n", start, first)
    if newline != -1:
        return -1
    if text.find("(", start, first) == -1:
        return first  # the common case: no parentheses inside the target
    depth = 0
    for i in range(start, limit):
        ch = text[i]
        if ch == "\n":
            return -1
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                return i
            depth -= 1
    return -1


def _scan_links(text: str, images: bool) -> Iterator[Tuple[int, int, str, str]]:
    """Yield (start, end, text, target) for [text](target), or ![alt](target) if images.

    Same rules as the former regexes: text has no "]" or newline (1-500 chars, 0-500 for
    images), the target has no ")" or newline (1-2000 chars), and plain links are not
    preceded by "!".
    """
    floor = 0
    pos = 0
    while True:
        idx = text.find("](", pos)
        if idx == -1:
            return
        pos = idx + 1
        lo = max(floor, idx - _TEXT_MAX - 2)
        window = text[lo:idx]
        cut = max(window.rfind("]"), window.rfind("\n")) + 1
        start = -1
        while True:
            cand = window.find("[", cut)
            if cand == -1:
                break
            bang = (lo + cand - 1 >= floor) and text[lo + cand - 1 : lo + cand] == "!"
            if bang == images:
                start = lo + cand - (1 if images else 0)
                text_start = lo + cand + 1
                break
            cut = cand + 1
        if start == -1:
            continue
        label = text[text_start:idx]
        if len(label) > _TEXT_MAX or (not images and not label):
            continue
        end = _target_end(text, idx + 2)
        if end == -1:
            continue
        target = text[idx + 2 : end]
        if not target or len(target) > _TARGET_MAX or "\n" in target:
            continue
        yield start, end + 1, label, target
        floor = pos = end + 1


def _scan_img_tags(text: str) -> Iterator[Tuple[int, int, str]]:
    """Yield (start, end, attrs) for <img ...> tags on a single line."""
    pos = 0
    while True:
        i = text.find("<img", pos)
        if i == -1:
            return
        pos = i + 4
        if text[pos : pos + 1] and (text[pos].isalnum() or text[pos] == "_"):
            continue
        end = text.find(">", pos, pos + _IMG_ATTRS_MAX + 2)
        if end == -1:
            continue
        raw = text[pos:end]
        if not raw or len(raw) > _IMG_ATTRS_MAX or "\n" in raw:
            continue
        yield i, end + 1, raw[:-1] if raw.endswith("/") and len(raw) > 1 else raw
        pos = end + 1


def _sub_links(text: str, replace) -> str:
    """Replace each [text](target) with replace(start, text, target) (None keeps it)."""
    out: List[str] = []
    last = 0
    for start, end, label, target in _scan_links(text, images=False):
        new = replace(start, label, target)
        if new is None:
            continue
        out.append(text[last:start])
        out.append(new)
        last = end
    if not out:
        return text
    out.append(text[last:])
    return "".join(out)


def _sub_images(text: str) -> str:
    """Reduce ![alt](src) to its alt text (empty alt leaves nothing)."""
    out: List[str] = []
    last = 0
    for start, end, alt, _target in _scan_links(text, images=True):
        out.append(text[last:start])
        out.append(alt)
        last = end
    out.append(text[last:])
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _strip_links(text: str) -> str:
    """Reduce [text](url) to text."""
    return _sub_links(text, lambda _start, label, _target: label)


# --- code masking -----------------------------------------------------------


class _Store(list):
    """Masked code snippets; .tail holds an unclosed fence that runs to the end of the text."""

    tail = ""


def _mask_code(text: str) -> Tuple[str, "_Store"]:
    """Replace fenced blocks and inline code spans with single-line placeholders.

    An unclosed fence swallows the rest of the text. It is not masked inline: it is returned
    in store.tail so no component can wrap it (its closing tag would land inside the fence).
    """
    lines = text.split("\n")
    store = _Store()
    out: List[str] = []
    i = 0
    n = len(lines)
    while i < n:
        m = _FENCE_OPEN_RE.match(lines[i])
        if m and not (m.group(2)[0] == "`" and "`" in m.group(3)):
            char, size = m.group(2)[0], len(m.group(2))
            close = re.compile(r"^[ \t]*" + re.escape(char) + "{%d,}[ \t]*$" % size)
            j = i + 1
            while j < n and not close.match(lines[j]):
                j += 1
            if j >= n:
                store.tail = ("\n" if out else "") + "\n".join(lines[i:])
                break
            end = j
            block = "\n".join(lines[i : end + 1])[len(m.group(1)) :]
            out.append(f"{m.group(1)}{_TOKEN_OPEN}F{len(store)}{_TOKEN_CLOSE}")
            store.append(block)
            i = end + 1
            continue
        out.append(lines[i])
        i += 1

    def inline(match):
        store.append(match.group(0))
        return f"{_TOKEN_OPEN}C{len(store) - 1}{_TOKEN_CLOSE}"

    return _INLINE_CODE_RE.sub(inline, "\n".join(out)), store


def _restore_all(text: str, store: "_Store") -> str:
    """Restore a whole document: placeholders plus any unclosed trailing fence."""
    return _restore_code(text, store) + store.tail


def _restore_code(text: str, store: List[str]) -> str:
    if not store:
        return text
    return _TOKEN_RE.sub(
        lambda m: store[int(m.group(2))] if int(m.group(2)) < len(store) else m.group(0), text
    )


def _fence_safe(method):
    """Run a text-transform method on content with code masked, then restore it.

    The mask store is exposed as self._code_store while the method runs, so helpers can
    read the original text behind a placeholder (for plain-text step titles).
    """

    def wrapper(self, content, *args, **kwargs):
        masked, store = _mask_code(content)
        previous = getattr(self, "_code_store", [])
        self._code_store = store
        try:
            result = method(self, masked, *args, **kwargs)
        finally:
            self._code_store = previous
        return _restore_all(result, store)

    wrapper.__name__ = method.__name__
    wrapper.__doc__ = method.__doc__
    return wrapper


# --- frontmatter ------------------------------------------------------------

_FM_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:(.*)$")


def _split_frontmatter(text: str) -> Tuple[Optional[List[str]], str]:
    """Return (frontmatter lines or None, body)."""
    if not text.startswith("---\n"):
        return None, text
    lines = text.split("\n")
    for idx in range(1, min(len(lines), 2000)):
        if lines[idx].rstrip() in ("---", "..."):
            inner = lines[1:idx]
            if not any(_FM_KEY_RE.match(ln) for ln in inner):
                return None, text
            if not all(not ln.strip() or ln[0] in " \t#-" or _FM_KEY_RE.match(ln) for ln in inner):
                return None, text
            return inner, "\n".join(lines[idx + 1 :])
    return None, text


def _fm_get(lines: List[str], key: str) -> Optional[str]:
    """Parsed scalar value for a top-level key, or None when the key is absent."""
    for ln in lines:
        m = _FM_KEY_RE.match(ln)
        if m and m.group(1) == key:
            raw = m.group(2).strip()
            if raw.startswith('"'):
                try:
                    return json.loads(raw)
                except ValueError:
                    return raw.strip('"')
            if raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
                return raw[1:-1].replace("''", "'")
            return raw
    return None


def _normalize(text: str) -> str:
    # U+E000/U+E001 are the code-mask placeholder delimiters; drop them from input so user
    # text can never be mistaken for (or forge) a placeholder.
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    return text.replace(_TOKEN_OPEN, "").replace(_TOKEN_CLOSE, "")


def _tidy_blank_lines(text: str) -> str:
    """Collapse runs of blank or whitespace-only lines to one blank line, outside code fences.

    Removing a component leaves its neighbours' blank lines behind; without this a second
    conversion pass would collapse them and the output would not be stable.
    """
    out: List[str] = []
    fence = ""
    for line in text.split("\n"):
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            if not fence:
                fence = marker.group(1)[0]
            elif marker.group(1)[0] == fence:
                fence = ""
        elif not fence and not line.strip():
            if out and not out[-1].strip():
                continue
            line = ""
        out.append(line)
    return "\n".join(out)


def _attr(value: str) -> str:
    return value.replace('"', "&quot;")


def sanitize_segment(segment: str) -> str:
    """A path segment Mintlify serves cleanly: dots (other than the extension) become hyphens."""
    return re.sub(r"[.\s]+", "-", segment).strip("-") or segment


def sanitize_page_key(key: str) -> str:
    """'api/docusaurus.config.js' -> 'api/docusaurus-config-js'."""
    return "/".join(sanitize_segment(part) for part in key.split("/"))


_TAG_RE = re.compile(r"<[A-Za-z][^<>]*>")
_TITLE_MARKUP_RE = re.compile(r"`([^`\n]+)`|\*\*([^*\n]+)\*\*|__([^_\n]+)__")


def clean_title(text: str) -> str:
    """Plain text for a page title: no inline code, emphasis, links or HTML entities.

    Mintlify prints titles and descriptions as written, so backticks would show up literally.
    """
    text = _strip_links(text)
    text = _TITLE_MARKUP_RE.sub(lambda m: m.group(1) or m.group(2) or m.group(3), text)
    text = re.sub(r"(?<![\w*])[*_](?!\s)([^*_\n]+?)(?<!\s)[*_](?![\w*])", r"\1", text)
    text = re.sub(
        r"^[\u2190-\u2BFF\U0001F000-\U0001FAFF\uFE0F\u200d\s]+", "", text
    )  # leading emoji
    return re.sub(r"\s+", " ", text).strip()


class SiteIndex:
    """What the converter needs to know about the whole site to rewrite links across pages.

    pages    page key -> {"title", "description", "dir", ...} (keys are output paths)
    rename   source page key -> output page key, for pages whose file name had to change
    routes   URL route (a doc's slug, or its path) -> output page key
    anchors  output page key -> {custom heading id: Mintlify anchor}
    snippets absolute source path of a partial -> its /snippets/ path
    prefixes URL prefixes Docusaurus served the docs under, e.g. "/docs"
    """

    def __init__(self) -> None:
        self.pages: Dict[str, Dict] = {}
        self.rename: Dict[str, str] = {}
        self.routes: Dict[str, str] = {}
        self.anchors: Dict[str, Dict[str, str]] = {}
        self.snippets: Dict[Path, str] = {}
        self.prefixes: List[str] = []

    def resolve(self, path: str) -> Optional[str]:
        """Output page key for a root-relative route such as '/docs/cli', or None."""
        route = "/" + path.strip("/")
        for prefix in self.prefixes:
            if route == prefix:
                route = "/"
            elif route.startswith(prefix + "/"):
                route = route[len(prefix) :]
        if route in self.routes:
            return self.routes[route]
        key = route.strip("/")
        for candidate in (key, key + "/index", key + "/README"):
            if candidate in self.rename:
                return self.rename[candidate]
            if candidate in self.pages:
                return candidate
        return None


class MintlifyConverter:
    def __init__(
        self,
        output_dir: Optional[Path] = None,
        download_assets: bool = False,
        input_root: Optional[Path] = None,
        static_dir: Optional[Path] = None,
        index: Optional[SiteIndex] = None,
        site_url: Optional[str] = None,
    ):
        self.output_dir = output_dir
        self.download_assets = download_assets
        self.input_root = input_root
        self.static_dir = Path(static_dir) if static_dir else None
        self.index = index
        self.site_url = site_url.rstrip("/") if site_url else None
        self.unresolved: List[str] = []
        self.outside: List[str] = []
        self.page_key: Optional[str] = None
        self.source_rel: Optional[str] = None
        self.current_file: Optional[Path] = None
        self.assets_copied: Dict[Path, Path] = {}
        self.files_copied: set = set()
        self.validation_errors: List[str] = []
        self.warnings: List[str] = []

    # --- extraction ---------------------------------------------------------

    def extract_title(self, content: str) -> str:
        """Frontmatter title if present, else the first H1 outside code, else 'Untitled'."""
        content = _normalize(content)
        fm, body = _split_frontmatter(content)
        if fm is not None:
            title = _fm_get(fm, "title")
            if title:
                return clean_title(title) or title
        masked, store = _mask_code(body)
        match = _H1_RE.search(masked)
        if match:
            title = re.sub(r"\s+#+$", "", match.group(1)).strip()
            if title:
                return clean_title(_restore_code(title, store)) or "Untitled"
        return "Untitled"

    def extract_description(self, content: str) -> str:
        """First prose paragraph (skipping headings, lists, quotes, code and JSX)."""
        content = _normalize(content)
        fm, body = _split_frontmatter(content)
        if fm is not None:
            existing = _fm_get(fm, "description")
            if existing:
                return existing
        masked, store = _mask_code(body)
        return self._first_prose(masked, store)

    def _first_prose(self, masked: str, store: "_Store") -> str:
        for block in re.split(r"\n[ \t]*\n", masked.strip("\n")):
            # Headings directly above prose do not hide it. The title heading is removed before
            # a second conversion, so deciding on the prose alone keeps both passes identical.
            block_lines = block.split("\n")
            skip = 0
            while skip < len(block_lines) and (
                not block_lines[skip].strip() or _HEADING_RE.match(block_lines[skip])
            ):
                skip += 1
            block_lines = block_lines[skip:]
            block = "\n".join(block_lines)
            first = block_lines[0] if block_lines else ""
            if (
                not block.strip()
                or _NON_PROSE_RE.match(first)
                or _TAB_LABEL_RE.match(first.strip())
            ):
                continue
            prose = []
            for line in block.split("\n"):
                if _NON_PROSE_RE.match(line) or _TAB_LABEL_RE.match(line.strip()):
                    break
                prose.append(line.strip())
            desc = re.sub(r"\{/\*.*?\*/\}", "", " ".join(prose))
            desc = _sub_images(desc)
            desc = re.sub(r"\[([^\]\n]{1,500})\]\[[^\]\n]*\]", r"\1", desc)
            desc = _strip_links(desc)
            desc = re.sub(r"\*\*([^*\n]{1,500})\*\*", r"\1", desc)
            desc = re.sub(r"\s+", " ", desc).strip()
            if not desc:
                continue
            desc = _restore_code(desc, store)
            desc = re.sub(r"`([^`\n]+)`", r"\1", desc)
            if desc.endswith(":"):
                continue  # "Options include:" introduces a list; it is not a summary
            if len(desc) > 200:
                desc = desc[:200].rstrip() + "..."
            return desc
        return ""

    # --- links --------------------------------------------------------------

    @_fence_safe
    def convert_api_links(self, content: str) -> str:
        """Convert API reference links to Mintlify format."""

        def replace(_start, label, target):
            m = re.fullmatch(r"/api/#operation/([^)\s]{1,500})", target)
            return f"[{label}](/api-reference/{m.group(1)})" if m else None

        return _sub_links(content, replace)

    def _rewrite_link_target(self, target: str, current_file: Optional[Path]) -> str:
        if not target or target.startswith("//") or _SCHEME_RE.match(target):
            return target
        if target.startswith("#"):
            return self._rewrite_anchor(self.page_key, target)
        m = re.search(r"[#?]", target)
        path, rest = (target[: m.start()], target[m.start() :]) if m else (target, "")
        original_path = path
        if "%" in path:
            path = unquote(path)
        had_ext = path.endswith((".md", ".mdx"))
        if had_ext:
            path = path.rsplit(".", 1)[0]
        raw_path = path
        relative_to_file = current_file is not None and not path.startswith("/")
        if current_file is not None and not path.startswith("/"):
            base = ""
            if self.input_root is not None:
                try:
                    rel = Path(os.path.abspath(current_file)).parent.relative_to(
                        Path(os.path.abspath(self.input_root))
                    )
                    base = rel.as_posix() if rel.as_posix() != "." else ""
                except ValueError:
                    pass
            norm = posixpath.normpath(posixpath.join(base, path))
            if norm == ".." or norm.startswith("../"):
                # Resolves outside the docs root: a root link would be dead, so keep it as written.
                if original_path not in self.outside:
                    self.outside.append(original_path)
                return target
            path = "/" if norm == "." else "/" + norm
        if self.index is not None and path.startswith("/"):
            key = self.index.resolve(path)
            if key is None and had_ext and relative_to_file:
                # Docusaurus also resolves a doc link written from the docs root.
                key = self.index.resolve("/" + posixpath.normpath(raw_path.lstrip("/")))
            if key is not None:
                return "/" + key + self._rewrite_anchor(key, rest)
            if len(path) > 1 and path.endswith("/"):
                path = path.rstrip("/")
            copied = self._link_asset(path)
            if copied:
                return copied + rest
            if self.site_url and not Path(path).suffix:
                return self.site_url + path + rest
            if path not in self.unresolved:
                self.unresolved.append(path)
            if "%" in original_path and unquote(original_path) == path:
                path = original_path
        return path + rest

    def _link_asset(self, path: str) -> Optional[str]:
        """Copy a file that a link points at (a PDF, a download) next to the pages."""
        if not self.download_assets or self.output_dir is None or not Path(path).suffix:
            return None
        rel = path.lstrip("/")
        roots = [r for r in (self.static_dir, self.input_root) if r is not None]
        for root in roots:
            root = Path(root).resolve()
            candidate = Path(os.path.normpath(root / rel))
            try:
                if (
                    candidate.is_file()
                    and not candidate.is_symlink()
                    and candidate.resolve().is_relative_to(root)
                    and candidate.suffix.lower() not in (".md", ".mdx")
                ):
                    dest = Path(self.output_dir) / rel
                    out_root = Path(self.output_dir)
                    below = [
                        dest,
                        *[q for q in dest.parents if out_root in q.parents or q == out_root],
                    ]
                    if any(q.is_symlink() for q in below if q != out_root):
                        return None
                    if dest.resolve().is_relative_to(Path(self.output_dir).resolve()):
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(candidate, dest)
                        self.files_copied.add(dest)
                        return "/" + rel
            except (OSError, RuntimeError):
                continue
        return None

    def _rewrite_anchor(self, key: Optional[str], rest: str) -> str:
        """Map a custom Docusaurus heading id to the anchor Mintlify generates for it."""
        if self.index is None or key is None or not rest.startswith("#"):
            return rest
        anchor = rest[1:]
        mapped = self.index.anchors.get(key, {}).get(anchor)
        return "#" + mapped if mapped else rest

    @_fence_safe
    def convert_relative_links(self, content: str, current_file: Optional[Path] = None) -> str:
        """Convert relative links to Mintlify paths (images are never touched)."""

        def replace_link(_start, text, raw):
            if text.startswith("!["):
                return None
            parts = re.match(r"""^(<[^<>]+>|\S+)(\s+(?:".*"|'.*'))?$""", raw.strip())
            if not parts:
                return None
            dest = parts.group(1)
            if dest.startswith("<"):
                target = self._rewrite_link_target(dest[1:-1], current_file)
                target = f"<{target}>" if " " in target else target
            else:
                target = self._rewrite_link_target(dest, current_file)
            return f'[{text}]({target}{parts.group(2) or ""})'

        content = _sub_links(content, replace_link)

        def linked_image(m):
            target = self._rewrite_link_target(m.group(2), current_file)
            return f"[{m.group(1)}]({target})"

        content = re.sub(
            r"\[(!\[[^\]\n]{0,300}\]\([^()\n]{1,500}\))\]\(([^()\s\n]{1,500})\)",
            linked_image,
            content,
        )

        def definition(m):
            target = m.group(2)
            angled = target.startswith("<") and target.endswith(">")
            new = self._rewrite_link_target(target[1:-1] if angled else target, current_file)
            return f"{m.group(1)}{'<' + new + '>' if angled else new}{m.group(3) or ''}"

        return re.sub(
            r"""^([ ]{0,3}\[[^\]\n]{1,200}\]:[ \t]*)(<[^>\n]+>|\S+)([ \t]+(?:"[^"\n]*"|'[^'\n]*'|\([^)\n]*\)))?[ \t]*$""",
            definition,
            content,
            flags=re.MULTILINE,
        )

    # --- images -------------------------------------------------------------

    def _asset_candidates(self, src: str, source_file: Path):
        """(candidate file, allowed root) pairs for an image reference, or None if non-local."""
        if src.lower().startswith("pathname://"):
            src = src[len("pathname://") :]
        if "\x00" in src or re.match(r"^[A-Za-z]:", src) or src.startswith(("\\", "//")):
            return None
        input_root = Path(
            self.input_root if self.input_root is not None else source_file.parent
        ).resolve()
        static = self.static_dir.resolve() if self.static_dir is not None else None
        rel = unquote(src.split("#")[0].split("?")[0])
        if rel.startswith("@site/static/") and static is not None:
            return [(static / rel[len("@site/static/") :], static)]
        if rel.startswith("@site/"):
            site_root = static.parent if static is not None else input_root.parent
            return [(site_root / rel[len("@site/") :], site_root)]
        if _SCHEME_RE.match(src):
            return None
        if rel.startswith("/"):
            # Docusaurus serves /img/x.png from the site's static folder.
            pairs = [(static / rel.lstrip("/"), static)] if static is not None else []
            pairs.append((input_root / rel.lstrip("/"), input_root))
            return pairs
        pairs = [(source_file.parent.resolve() / rel, input_root)]
        if static is not None:
            pairs.append((static / rel, static))
        return pairs

    def _copy_asset(self, src: str, source_file: Path) -> Optional[str]:
        """Copy a local image into <output>/images and return its URL, or None."""
        if not self.download_assets or self.output_dir is None:
            return None
        pairs = self._asset_candidates(src, source_file)
        if (
            src.startswith("/images/")
            and pairs
            and not any(Path(os.path.normpath(raw)).is_file() for raw, _ in pairs)
        ):
            return None  # already converted: the file was copied on an earlier run
        if pairs is None:
            self.warnings.append(f"Skipped image with non-local path: {src}")
            return None
        if Path(src.split("#")[0].split("?")[0]).suffix.lower() not in IMAGE_EXTENSIONS:
            self.warnings.append(f"Skipped image with unsupported extension: {src}")
            return None
        found = None
        for raw, root in pairs:
            candidate = Path(os.path.normpath(raw))
            try:
                resolved = candidate.resolve()
                inside = resolved.is_relative_to(root)
            except (OSError, RuntimeError):
                continue
            if not inside:
                continue
            if resolved != candidate or candidate.is_symlink():
                self.warnings.append(f"Skipped symlinked image: {src}")
                return None
            if candidate.is_file():
                found = candidate
                break
        if found is None:
            if any(
                Path(os.path.normpath(raw)).resolve().is_relative_to(root) for raw, root in pairs
            ):
                self.warnings.append(f"Image not found: {src}")
            else:
                self.warnings.append(f"Skipped image outside the input directory: {src}")
            return None
        candidate = found

        if candidate in self.assets_copied:
            return f"/images/{self.assets_copied[candidate].name}"
        assets_dir = Path(self.output_dir) / "images"
        if assets_dir.is_symlink():
            self.warnings.append("Skipped image copy: output images directory is a symlink")
            return None
        name = re.sub(r"[^\w.\-]", "_", candidate.name)
        stem, ext = os.path.splitext(name)
        dest = assets_dir / name
        counter = 1
        while dest in self.assets_copied.values():
            dest = assets_dir / f"{stem}_{counter}{ext}"
            counter += 1
        if dest.is_symlink():
            self.warnings.append(f"Skipped image copy over symlink: {dest.name}")
            return None
        assets_dir.mkdir(parents=True, exist_ok=True)
        if not (dest.exists() and os.path.samefile(candidate, dest)):
            shutil.copyfile(candidate, dest)
        self.assets_copied[candidate] = dest
        return f"/images/{dest.name}"

    @_fence_safe
    def handle_images(self, content: str, source_file: Optional[Path] = None) -> str:
        """Wrap images in Frame (single pass); copy local assets when enabled and safe.

        Images already inside a Frame (a themed light/dark pair) keep their wrapper and only
        have their source rewritten. <img> attributes such as className and width are kept.
        """

        frames = [m.span() for m in re.finditer(r"<Frame\b[^>]*>.*?</Frame>", content, re.DOTALL)]

        def in_frame(pos: int) -> bool:
            return any(a < pos < b for a, b in frames)

        found = []
        for start, end, alt, raw in _scan_links(content, images=True):
            parts = re.match(
                r"""^(?:<([^<>]+)>|(\S+))(?:\s+(?:"([^"]*)"|'([^']*)'))?$""", raw.strip()
            )
            src = (parts.group(1) or parts.group(2)) if parts else raw.strip()
            caption = (parts.group(3) or parts.group(4) or "") if parts else ""
            found.append((start, end, alt, src, caption, None))
        for start, end, attrs in _scan_img_tags(content):
            s = re.search(r'\bsrc=(?:"([^"]*)"|\'([^\']*)\')', attrs)
            if not s:
                continue
            a = re.search(r'\balt=(?:"([^"]*)"|\'([^\']*)\')', attrs)
            src = s.group(1) if s.group(1) is not None else s.group(2)
            alt = (a.group(1) if a.group(1) is not None else a.group(2)) if a else ""
            found.append((start, end, alt, src, "", attrs))
        found.sort(key=lambda item: item[0])

        out: List[str] = []
        last = 0
        for start, end, alt, src, caption, attrs in found:
            if start < last:
                continue
            if src.lower().startswith("file:"):
                self.warnings.append(f"Skipped image with file: source: {src}")
                continue
            if src.startswith("//") or re.match(r"^(?:https?|data):", src, re.IGNORECASE):
                if (
                    attrs is None
                    and not in_frame(start)
                    and self._alone_on_line(content, start, end)
                ):
                    # A remote image on its own line is framed too; there is nothing to copy.
                    out.append(content[last:start])
                    out.append(self._wrap_image_in_frame(alt, src, caption))
                    last = end
                continue
            if content[start - 1 : start] == "[":
                # An image that is the label of a link: keep it Markdown, but copy the file.
                if attrs is None and source_file is not None:
                    new_src = self._copy_asset(src, source_file)
                    if new_src:
                        out.append(content[last:start])
                        title = f' "{caption}"' if caption else ""
                        out.append(f"![{alt}]({new_src}{title})")
                        last = end
                continue
            if source_file is not None:
                new_src = self._copy_asset(src, source_file)
                if new_src:
                    src = new_src
            out.append(content[last:start])
            if attrs is not None and in_frame(start):
                out.append(self._img_tag(attrs, src, alt))
            elif attrs is not None:
                out.append(
                    self._own_lines(
                        content, start, end, self._wrap_image_in_frame(alt, src, caption, attrs)
                    )
                )
            elif in_frame(start):
                out.append(self._img_tag(None, src, alt))
            else:
                out.append(
                    self._own_lines(
                        content, start, end, self._wrap_image_in_frame(alt, src, caption)
                    )
                )
            last = end
        if not out:
            return content
        out.append(content[last:])
        return "".join(out)

    @staticmethod
    def _alt_from_name(src: str) -> str:
        """Alt text for an image written without any: its file name, spaced out."""
        stem = Path(src.split("#")[0].split("?")[0]).stem
        words = re.sub(r"[-_.]+", " ", stem).strip()
        return (
            words[:1].upper() + words[1:]
            if words and not words.isdigit()
            else "Documentation image"
        )

    @staticmethod
    def _own_lines(content: str, start: int, end: int, block: str) -> str:
        """A Frame is a block: when prose surrounds the image, give the Frame its own lines."""
        return docusaurus._own_lines(content, start, end, block)

    @staticmethod
    def _alone_on_line(content: str, start: int, end: int) -> bool:
        line_start = content.rfind("\n", 0, start) + 1
        line_end = content.find("\n", end)
        line_end = len(content) if line_end == -1 else line_end
        return not content[line_start:start].strip() and not content[end:line_end].strip()

    def _img_tag(self, attrs: Optional[str], src: str, alt: str) -> str:
        """An <img /> tag; other attributes of an existing tag are kept, src and alt replaced."""
        alt = alt.strip() if alt and alt.strip() else self._alt_from_name(src)
        if attrs is None:
            return f'<img src="{_attr(src)}" alt="{_attr(alt)}" />'
        attrs = re.sub(
            r'\bsrc=(?:"[^"]*"|\'[^\']*\')', lambda _m: f'src="{_attr(src)}"', attrs, count=1
        )
        if re.search(r'\balt=(?:"[^"]*"|\'[^\']*\')', attrs):
            attrs = re.sub(
                r'\balt=(?:"[^"]*"|\'[^\']*\')', lambda _m: f'alt="{_attr(alt)}"', attrs, count=1
            )
        else:
            attrs = attrs.rstrip() + f' alt="{_attr(alt)}"'
        attrs = re.sub(r"[ \t]*\n[ \t]*", " ", attrs).rstrip()
        return f"<img{attrs} />"

    def _wrap_image_in_frame(
        self, alt: str, src: str, caption: str = "", attrs: Optional[str] = None
    ) -> str:
        """Wrap image in a Frame component with non-empty alt text (and the title as caption)."""
        opener = f'<Frame caption="{_attr(caption)}">' if caption else "<Frame>"
        return f"{opener}\n  {self._img_tag(attrs, src, alt)}\n</Frame>"

    # --- callouts and banners -----------------------------------------------

    @_fence_safe
    def convert_callouts(self, content: str) -> str:
        """Convert blockquotes to Warning/Note/Tip/Info/Check components."""
        result: List[str] = []
        quote: List[str] = []
        raw: List[str] = []

        def flush():
            if any(_FENCE_OPEN_RE.match(q) for q in quote):
                # Unquoting would create a code fence and change how the page masks code.
                result.extend(raw)
            else:
                text = "\n".join(quote)
                tag = self._get_proper_callout_component(self._determine_callout_type(text))
                result.extend([f"<{tag}>", text, f"</{tag}>"])
            quote.clear()
            raw.clear()

        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith(">"):
                quote.append(stripped[1:].strip())
                raw.append(line)
                continue
            if quote:
                flush()
            result.append(line)
        if quote:
            flush()
        return "\n".join(result)

    def _determine_callout_type(self, text: str) -> str:
        """Pick a callout type from its leading label, else from keywords."""
        label = re.match(
            r"^\W*(warning|caution|danger|critical|important|note|tip|hint|info|success)\b",
            text,
            re.IGNORECASE,
        )
        if label:
            word = label.group(1).lower()
            if word in ("warning", "caution", "critical", "important"):
                return "warning"
            return {
                "danger": "danger",
                "note": "note",
                "tip": "tip",
                "hint": "tip",
                "info": "info",
                "success": "check",
            }[word]

        def has(*words):
            return re.search(r"\b(?:" + "|".join(words) + r")\b", text, re.IGNORECASE) is not None

        if has("warning", "caution", "critical", "danger", "important"):
            return "warning"
        if has("tip", "hint", "best practice", "pro tip"):
            return "tip"
        if has("note", "remember", "additional"):
            return "note"
        if has("success", "complete", "done", "achieved"):
            return "check"
        return "info"

    def _get_proper_callout_component(self, callout_type: str) -> str:
        component_map = {
            "warning": "Warning",
            "danger": "Danger",
            "tip": "Tip",
            "note": "Note",
            "info": "Info",
            "check": "Check",
        }
        return component_map.get(callout_type, "Info")

    @_fence_safe
    def convert_banner(self, content: str) -> str:
        """Convert 'Deprecated:'/'Important:'/'Notice:'/'Alert:' paragraphs to Banner."""
        pattern = (
            r"(?:\A|(?<=\n\n))(?:(?:⚠️?|\U0001f6a8|\U0001f4e2|\U0001f4a1)[ \t]*)?"
            r"(Deprecated|Important|Notice|Alert):[ \t]*([^\n]+(?:\n(?![ \t]*\n)(?!"
            + _TAG_LINE
            + r")[^\n]+)*)"
        )
        type_map = {
            "deprecated": "warning",
            "important": "warning",
            "notice": "info",
            "alert": "warning",
        }

        def replacer(match):
            if any(_FENCE_OPEN_RE.match(ln) for ln in match.group(2).split("\n")):
                return match.group(0)
            kind = type_map.get(match.group(1).lower(), "info")
            return f'<Banner type="{kind}">\n  {match.group(2).strip()}\n</Banner>'

        return re.sub(pattern, replacer, content)

    # --- accordions ---------------------------------------------------------

    @_fence_safe
    def convert_accordions(self, content: str) -> str:
        """Wrap FAQ/troubleshooting/advanced-style H3 sections in Accordion.

        A section runs to the next heading of any level (or an existing Accordion).
        """
        lines = content.split("\n")
        result: List[str] = []
        i = 0
        while i < len(lines):
            h3 = re.match(r"^###[ \t]+(.+?)[ \t]*$", lines[i])
            if not h3 or not self._should_be_accordion(h3.group(1)):
                result.append(lines[i])
                i += 1
                continue
            j = i + 1
            while j < len(lines) and not re.match(r"^(?:#{1,6}[ \t]+|<Accordion\b)", lines[j]):
                j += 1
            section = lines[i + 1 : j]
            while section and not section[0].strip():
                section.pop(0)
            trailing = 0
            while section and not section[-1].strip():
                section.pop()
                trailing += 1
            if not section:
                result.append(lines[i])
                i += 1
                continue
            result.append(f'<Accordion title="{_attr(h3.group(1))}">')
            result.extend(section)
            result.append("</Accordion>")
            result.extend([""] * trailing)
            i = j
        return "\n".join(result)

    _ACCORDION_RE = re.compile(
        r"\b(?:troubleshooting|faqs?|frequently asked|advanced|common issues|known issues|"
        r"error codes|walkthrough|step by step|break ?down)\b",
        re.IGNORECASE,
    )

    def _should_be_accordion(self, title: str) -> bool:
        """Only explicit FAQ/troubleshooting/advanced-style headings become accordions."""
        return self._ACCORDION_RE.search(title) is not None

    # --- tabs ---------------------------------------------------------------

    @_fence_safe
    def convert_tabs(self, content: str) -> str:
        """Turn consecutive 'Language:' labelled blocks into one Tabs group.

        A block is a label followed by lines up to the next blank line or label; blank lines
        between blocks are allowed. A group needs two or more non-empty blocks, otherwise the
        original lines are kept as they were.
        """
        lines = content.split("\n")
        n = len(lines)
        result: List[str] = []
        i = 0
        while i < n:
            if not _TAB_LABEL_RE.match(lines[i].strip()):
                result.append(lines[i])
                i += 1
                continue
            start = i
            tabs: List[Tuple[str, str]] = []
            j = i
            while True:
                label = _TAB_LABEL_RE.match(lines[j].strip())
                assert label is not None  # j only advances over matching label lines
                lang = label.group(1)
                k = j + 1
                buf: List[str] = []
                while (
                    k < n
                    and lines[k].strip()
                    and not _TAB_LABEL_RE.match(lines[k].strip())
                    and not _COMPONENT_LINE_RE.match(lines[k])
                ):
                    buf.append(lines[k])
                    k += 1
                if buf:
                    tabs.append((lang, "\n".join(buf).strip()))
                nxt = k
                while nxt < n and not lines[nxt].strip():
                    nxt += 1
                if nxt < n and _TAB_LABEL_RE.match(lines[nxt].strip()):
                    j = nxt
                    continue
                end = k
                break

            if len(tabs) > 1:
                result.append("<Tabs>")
                for lang, code in tabs:
                    result.append(f'  <Tab title="{self._get_proper_language_name(lang)}">')
                    if _TOKEN_OPEN + "F" in code or "```" in code:
                        # Already holds its own fenced code; an outer fence would be closed by it.
                        result.append(code)
                    else:
                        result.extend([f"```{lang.lower()}", code, "```"])
                    result.append("  </Tab>")
                result.append("</Tabs>")
            else:
                result.extend(lines[start:end])
            i = end
        return "\n".join(result)

    def _get_proper_language_name(self, lang: str) -> str:
        language_map = {
            "javascript": "JavaScript",
            "python": "Python",
            "typescript": "TypeScript",
            "ruby": "Ruby",
            "go": "Go",
            "java": "Java",
            "php": "PHP",
            "curl": "cURL",
            "node.js": "Node.js",
            "react": "React",
            "vue": "Vue.js",
            "angular": "Angular",
            "bash": "Bash",
            "shell": "Shell",
            "powershell": "PowerShell",
        }
        return language_map.get(lang.lower(), lang)

    # --- lists and steps ----------------------------------------------------

    @_fence_safe
    def convert_lists_with_bold_headers(self, content: str) -> str:
        """Normalise '* **Label** text' to '* **Label**: text' (no doubled colon)."""
        pattern = r"^([ \t]*[*\-])[ \t]+\*\*([^*\n]{1,200})\*\*[ \t]+([^\n]+)$"

        def replacer(match):
            header, rest = match.group(2), match.group(3)
            if header.endswith(":") or re.match(r"[-:\u2013\u2014]", rest):
                return match.group(0)
            return f"{match.group(1)} **{header}**: {rest}"

        return re.sub(pattern, replacer, content, flags=re.MULTILINE)

    @_fence_safe
    def convert_numbered_steps(self, content: str) -> str:
        """Convert each numbered list to one Steps component.

        A list continues across blank lines, indented content and fenced code between
        numbered items (they belong to the previous step). It ends at the first line that is
        non-blank, not indented, not a fence and not numbered, once a blank line has been seen.
        """
        lines = content.split("\n")
        n = len(lines)
        result: List[str] = []
        num_re = _NumberedItem()
        fence = _TOKEN_OPEN + "F"

        def flush(steps: List[str]):
            result.append("<Steps>")
            for idx, step in enumerate(steps, 1):
                result.append(f'  <Step title="{_attr(self._extract_step_title(step, idx))}">')
                result.append(f"  {step}")
                result.append("  </Step>")
            result.append("</Steps>")

        i = 0
        while i < n:
            match = num_re.match(lines[i])
            if not match:
                result.append(lines[i])
                i += 1
                continue
            steps: List[str] = []
            list_start = i
            while match:
                body = [match.group(2)]
                i += 1
                seen_blank = False
                while i < n and not num_re.match(lines[i]):
                    line = lines[i]
                    if not line.strip():
                        seen_blank = True
                    elif line[0] not in " \t" and not line.startswith(fence):
                        # Unindented text continues the step only directly after it, and
                        # never swallows a heading, quote, JSX block or table.
                        if seen_blank or _BLOCK_START_RE.match(line):
                            break
                    body.append(line)
                    i += 1
                trailing = 0
                while body and not body[-1].strip():
                    body.pop()
                    trailing += 1
                match = num_re.match(lines[i]) if i < n else None
                if not match:
                    i -= trailing
                steps.append("\n".join(body))
            if self._is_procedure(steps):
                flush(steps)
            else:
                result.extend(lines[list_start:i])  # a list of facts or questions stays a list
        return "\n".join(result)

    def _is_procedure(self, steps: List[str]) -> bool:
        """Steps are for procedures. Not for a list of questions, or of long sentences that
        would make run-on step titles."""
        long_items = 0
        for step in steps:
            first = self._plain_inline(step.split("\n")[0]).strip()
            if first.endswith("?"):
                return False
            sentence_end = re.search(r"[.!?;:](?=\s|$)", first)
            if len(first) > 80 and (sentence_end is None or sentence_end.start() > 80):
                long_items += 1
        return long_items * 2 <= len(steps)

    def _plain_inline(self, text: str) -> str:
        """Text with inline code, links and emphasis markers reduced to plain words."""
        store = getattr(self, "_code_store", [])

        def code(m):
            idx = int(m.group(2))
            if m.group(1) != "C" or idx >= len(store):
                return ""
            return store[idx].strip("`").strip()

        text = _TOKEN_RE.sub(code, text)
        text = _strip_links(text)
        text = re.sub(r"(\*\*|__)([^\n]{1,200}?)\1", r"\2", text)
        text = re.sub(r"(?<![\w*])\*(?!\s)([^*\n]{1,200}?)(?<!\s)\*(?![\w*])", r"\1", text)
        text = re.sub(r"(?<![\w_])_(?!\s)([^_\n]{1,200}?)(?<!\s)_(?![\w_])", r"\1", text)
        return text.replace("**", "").replace("`", "")

    def _extract_step_title(self, step_content: str, index: int = 1) -> str:
        """Plain-text step title: first clause of the first line, at most ~80 characters."""
        first = step_content.split("\n")[0].strip()
        stripped = _STEP_PREFIX_RE.sub("", first, count=1)
        if stripped and stripped.lower() not in ("step", "steps"):
            first = stripped
        title = re.sub(r"\s+", " ", self._plain_inline(first)).strip()
        # A tag name in a title (`<em>` written as code) must not read as a tag.
        title = re.sub(r"<(/?[A-Za-z][^<>\n]*)>", r"\1", title)
        for m in re.finditer(r"[.!?;](?=\s|$)", title):
            if m.start() >= 12:
                title = title[: m.start()]
                break
        if len(title) > 80:
            cut = title.rfind(" ", 0, 81)
            if cut <= 0:
                cut = title.find(" ")
            title = title[:cut] if cut > 0 else title
        title = title.rstrip(" ,;:-\u2013\u2014(").strip()
        if not title or title.lower() in ("step", "steps"):
            return f"Step {index}"
        return title

    # --- option lists -------------------------------------------------------

    @_fence_safe
    def convert_option_fields(self, content: str) -> str:
        """Under a heading named after code, turn '- Type: `x`' / '- Default: `y`' bullets into
        a ParamField. The heading stays, so its anchor and table-of-contents entry survive."""
        pattern = re.compile(
            r"^(#{2,5}[ \t]+(?:" + _TOKEN_OPEN + r"C(\d+)" + _TOKEN_CLOSE + r"))[ \t]*\n\n"
            r"((?:[-*][ \t]+(?:Type|Default|Required)\b[^\n]*\n)+)",
            re.MULTILINE,
        )
        store = getattr(self, "_code_store", [])

        def plain(token: str) -> str:
            return _restore_code(token, store).replace("`", "").strip()

        def replace(m):
            name = store[int(m.group(2))].strip("`").strip() if int(m.group(2)) < len(store) else ""
            fields = {}
            for line in m.group(3).strip().split("\n"):
                f = re.match(r"[-*][ \t]+(Type|Default|Required)\b[ \t]*:?[ \t]*(.*)$", line)
                if f:
                    fields[f.group(1).lower()] = plain(f.group(2))
            if not name or "type" not in fields or not re.fullmatch(r"[\w.$\-\[\]]+", name):
                return m.group(0)
            attrs = f'path="{_attr(name)}" type="{_attr(fields["type"])}"'
            if fields.get("default"):
                attrs += f' default="{_attr(fields["default"])}"'
            if fields.get("required", "").lower() in ("true", "yes"):
                attrs += " required"
            return f"{m.group(1)}\n\n<ParamField {attrs} />\n"

        return pattern.sub(replace, content)

    # --- help cards ---------------------------------------------------------

    @_fence_safe
    def convert_emoji(self, content: str) -> str:
        """Replace emoji in prose with Mintlify <Icon /> tags (Lucide names)."""
        dropped: set = set()
        content = _TAG_RE.sub(
            lambda m: m.group(0) if m.group(0).startswith("<Icon") else strip_emoji(m.group(0)),
            content,
        )
        out = "\n".join(convert_emoji_line(ln, dropped) for ln in content.split("\n"))
        if dropped:
            self.warnings.append(
                "No icon for " + " ".join(sorted(dropped)) + "; removed from the page"
            )
        return out

    @_fence_safe
    def convert_help_sections(self, content: str) -> str:
        """Convert 'Need help?'-style paragraphs to Card components."""
        pattern = (
            r"(?:\A|(?<=\n\n))(Need help\?|Questions\?|Support|Contact us|Get help"
            r"|Need assistance|Stuck\?|Having trouble\?)"
            r"[ \t]*\n+((?!" + _TAG_LINE + r")(?:[^\n]+\n(?!" + _TAG_LINE + r"))*[^\n]+)"
        )

        def replacer(match):
            title, text = match.group(1), match.group(2).strip()
            icon = self._get_help_section_icon(title, text)
            body = self._clean_help_section_text(text)
            return f'<Card title="{title}" icon="{icon}">\n  {body}\n</Card>'

        return re.sub(pattern, replacer, content)

    def _get_help_section_icon(self, title: str, text: str) -> str:
        title_lower = title.lower()
        text_lower = text.lower()
        if any(word in title_lower for word in ["support", "contact"]):
            return "headphones"
        elif any(word in title_lower for word in ["questions", "stuck", "trouble"]):
            return "circle-help"
        elif any(word in text_lower for word in ["community", "discord", "forum"]):
            return "users"
        elif any(word in text_lower for word in ["documentation", "docs", "guide"]):
            return "book-open"
        return "circle-help"

    def _clean_help_section_text(self, text: str) -> str:
        return "\n".join(line.strip() for line in text.split("\n") if line.strip())

    # --- Docusaurus syntax --------------------------------------------------

    @_fence_safe
    def convert_docusaurus(self, content: str) -> str:
        """Rewrite Docusaurus-only syntax: imports, heading ids, comments, admonitions,
        TabItem tabs, <details> and the inline Docusaurus components."""
        first = len(self.warnings)
        removed: Dict[str, str] = {}
        text = docusaurus.remove_imports(content, removed, self._snippet_for)
        # With a site index, links to renamed anchors are rewritten, so no warning is needed.
        text = docusaurus.strip_heading_ids(text, None if self.index is not None else self.warnings)
        text = docusaurus.convert_html_comments(text)
        text = docusaurus.convert_inline_components(
            text,
            self.warnings,
            page_url=("/" + self.page_key) if self.page_key else None,
            source_path=self.source_rel,
            doc_cards=self._doc_cards(),
        )
        text = docusaurus.convert_admonitions(text, self.warnings)
        text = docusaurus.convert_tabs(text)
        text = docusaurus.convert_details(text)
        text = docusaurus.convert_admonition_components(text)
        text = docusaurus.drop_runtime_exports(text, self.warnings)
        text = docusaurus.convert_require_links(text)
        text = docusaurus.convert_code_components(text, self._restore_masked, self._stash_masked)
        text = docusaurus.convert_image_components(text, removed)
        text = docusaurus.normalize_img_sources(text)
        text = docusaurus.neutralize_unknown_components(text, self.warnings, removed)
        self.warnings[first:] = [_restore_code(w, self._code_store) for w in self.warnings[first:]]
        return text

    def _restore_masked(self, text: str) -> str:
        return _restore_code(text, self._code_store)

    def _stash_masked(self, block: str) -> str:
        """Hide generated code from later rewrites by storing it like masked code."""
        self._code_store.append(block)
        return f"{_TOKEN_OPEN}F{len(self._code_store) - 1}{_TOKEN_CLOSE}"

    def _snippet_for(self, module: str) -> Optional[str]:
        """The /snippets/ path of an imported partial that was converted into a snippet."""
        if self.index is None or self.current_file is None or not module.startswith("."):
            return None
        target = Path(os.path.normpath(Path(self.current_file).resolve().parent / module))
        return self.index.snippets.get(target)

    def _doc_cards(self) -> Optional[str]:
        """A CardGroup linking the pages that sit under this page's folder (<DocCardList />)."""
        if self.index is None or not self.page_key:
            return None
        folder = self.page_key.rsplit("/", 1)[0] if "/" in self.page_key else ""
        if self.page_key.rsplit("/", 1)[-1] not in ("index", "README"):
            folder = self.page_key
        cards = []
        for key, info in sorted(
            self.index.pages.items(),
            key=lambda kv: (kv[1].get("position") is None, kv[1].get("position") or 0, kv[0]),
        ):
            if key == self.page_key:
                continue
            parent = key.rsplit("/", 1)[0] if "/" in key else ""
            leaf = key.rsplit("/", 1)[-1]
            if parent == folder or (
                leaf in ("index", "README") and parent.rsplit("/", 1)[0] == folder and "/" in parent
            ):
                cards.append((key, info))
        if not cards:
            return None
        lines = ["<CardGroup cols={2}>"]
        for key, info in cards:
            attrs = f'title="{_attr(info.get("title") or key)}" href="/{key}"'
            desc = info.get("description") or ""
            # The description is plain text in an MDX body: angle brackets and braces are escaped.
            desc = desc.replace("<", "&lt;").replace("{", "\\{").replace("}", "\\}")
            lines.append(f"  <Card {attrs}>")
            if desc:
                lines.append(f"    {desc}")
            lines.append("  </Card>")
        lines.append("</CardGroup>")
        return "\n".join(lines)

    def convert_code_blocks(self, content: str) -> str:
        """Apply Mintlify code block options to each fenced block."""
        masked, store = _mask_code(content)
        for m in _TOKEN_RE.finditer(masked):
            if m.group(1) == "F" and int(m.group(2)) < len(store):
                idx = int(m.group(2))
                store[idx] = docusaurus.convert_fence(store[idx])
        return _restore_all(masked, store)

    # --- validation ---------------------------------------------------------

    def validate_mdx(self, content: str) -> List[str]:
        """Report unclosed or mismatched tags, ignoring anything inside code."""
        _, body = _split_frontmatter(_normalize(content))
        masked, _ = _mask_code(body)
        masked = re.sub(r"\{/\*.*?\*/\}", "", masked, flags=re.DOTALL)
        errors: List[str] = []
        stack: List[str] = []
        skip_until = 0
        for match in re.finditer(r"</?\w+", masked):
            if match.start() < skip_until:
                continue
            name = match.group(0).lstrip("</")
            end = match.end()
            if match.group(0).startswith("</"):
                if masked[end : end + 1] != ">":
                    continue
                skip_until = end + 1
                if stack and stack[-1] == name:
                    stack.pop()
                else:
                    errors.append(f"Unclosed or mismatched tag: </{name}>")
                continue
            nxt = masked[end : end + 1]
            if nxt == ">":
                tag_end = end
            elif nxt.isspace():
                # A ">" inside a quoted attribute value (type="a => b") does not end the tag.
                closing = re.compile(r"""(?:[^>"']|"[^"\n]*"|'[^'\n]*')*>""").match(
                    masked, end, end + 1002
                )
                if closing is None:
                    continue
                tag_end = closing.end() - 1
            else:
                continue
            skip_until = tag_end + 1
            if name.lower() in _VOID_TAGS or masked[end:tag_end].rstrip().endswith("/"):
                continue
            stack.append(name)
        if stack:
            errors.append(f"Unclosed tags: {', '.join(stack)}")
        return errors

    # --- frontmatter and title ----------------------------------------------

    @staticmethod
    def _title_from_path(path: Path) -> str:
        """A page with no title and no heading is named after its file (or its folder)."""
        stem = path.with_suffix("").name
        if stem.lower() in ("index", "readme") and path.parent.name:
            stem = path.parent.name
        words = re.sub(r"[-_.]+", " ", stem).strip()
        return (words[:1].upper() + words[1:]) if words else "Untitled"

    @staticmethod
    def _fold_block_scalars(lines: List[str]) -> List[str]:
        """'description: >' followed by indented lines becomes one quoted string; Mintlify's
        frontmatter reader and this tool both want single-line values."""
        out: List[str] = []
        i = 0
        while i < len(lines):
            if re.match(r"^(title|description|sidebar_label)\s*:\s*$", lines[i]) and not (
                i + 1 < len(lines) and lines[i + 1][:1] in (" ", "\t")
            ):
                i += 1  # an empty value is the same as none: the title comes from the heading
                continue
            q = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(['\"])(.*)$", lines[i])
            if (
                q
                and q.group(2) not in q.group(3)
                and i + 1 < len(lines)
                and lines[i + 1][:1] in " \t"
            ):
                j = i + 1
                block = [q.group(3).strip()]
                while j < len(lines) and lines[j][:1] in " \t":
                    block.append(lines[j].strip().rstrip(q.group(2)))
                    if q.group(2) in lines[j]:
                        j += 1
                        break
                    j += 1
                out.append(f"{q.group(1)}: {json.dumps(' '.join(block), ensure_ascii=False)}")
                i = j
                continue
            m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*[>|][+-]?\d*\s*$", lines[i])
            if not m:
                out.append(lines[i])
                i += 1
                continue
            j = i + 1
            block = []
            while j < len(lines) and (not lines[j].strip() or lines[j][0] in " \t"):
                block.append(lines[j].strip())
                j += 1
            text = re.sub(r"\s+", " ", " ".join(block)).strip()
            out.append(f"{m.group(1)}: {json.dumps(text, ensure_ascii=False)}")
            i = j
        return out

    _YAML_HAZARD = re.compile(r"""(:\s|\s#|^[\[\]{}&*!|>'"%@`-]|:$)""")

    @classmethod
    def _clean_fm_line(cls, line: str) -> str:
        """Titles and sidebar labels are printed as written, so strip Markdown from them; a
        plain value that YAML would misread ('Other: with colon') is quoted."""
        m = re.match(r"^(title|sidebarTitle|description)\s*:(.*)$", line)
        if not m:
            return line
        key = m.group(1)
        value = _fm_get([line], key) or ""
        cleaned = clean_title(value) if key != "description" else value
        raw = m.group(2).strip()
        quoted = raw[:1] in ("'", '"')
        if (cleaned and cleaned != value) or (not quoted and cls._YAML_HAZARD.search(raw)):
            return f"{key}: {json.dumps(cleaned or value, ensure_ascii=False)}"
        return line

    def create_frontmatter(
        self, title: str, description: str = "", icon: str = "", mode: str = ""
    ) -> str:
        """Create Mintlify frontmatter (values are JSON-escaped YAML strings)."""
        fm = ["---", f"title: {json.dumps(title, ensure_ascii=False)}"]
        if description:
            fm.append(f"description: {json.dumps(description, ensure_ascii=False)}")
        if icon:
            fm.append(f"icon: {json.dumps(icon, ensure_ascii=False)}")
        if mode:
            fm.append(f"mode: {json.dumps(mode, ensure_ascii=False)}")
        fm.append("---")
        return "\n".join(fm)

    def remove_original_title(self, content: str, expected_title: Optional[str] = None) -> str:
        """Remove the title heading so it is not repeated under the frontmatter title.

        Without expected_title (the title came from the heading) the first H1 is removed and,
        if it led the content, so is any directly following H1 with the same text. With
        expected_title (frontmatter already has it) only leading H1s with that text are removed.
        Both rules leave nothing for a second pass to remove, so conversion is idempotent.
        """
        masked, store = _mask_code(content)

        def h1_text(m):
            return _restore_code(re.sub(r"\s+#+$", "", m.group(1)).strip(), store)

        if expected_title is None:
            match = _H1_RE.search(masked)
            if not match:
                return content
            expected_title = h1_text(match)
            leading = not masked[: match.start()].strip()
            masked = masked[: match.start()] + masked[match.end() :].lstrip("\n")
            if not leading:
                return _restore_all(masked, store)
        # Walk forward by index: slicing the text on every removed heading is quadratic.
        pos = cut = 0
        while True:
            while masked.startswith("\n", pos):
                pos += 1
            match = _H1_RE.match(masked, pos)
            if not match or h1_text(match) != expected_title:
                break
            pos = match.end()
            while masked.startswith("\n", pos):
                pos += 1
            cut = pos
        if cut:
            masked = masked[cut:]
        return _restore_all(masked, store)

    # --- main entry point ---------------------------------------------------

    def convert(self, mdx_content: str, source_file: Optional[Path] = None, **kwargs) -> str:
        """Convert MDX text to Mintlify format. Raises ValueError for oversized input."""
        self.validation_errors = []
        self.warnings = []
        if (
            len(mdx_content) > MAX_INPUT_BYTES
            or len(mdx_content.encode("utf-8", "ignore")) > MAX_INPUT_BYTES
        ):
            raise ValueError(f"Input is too large ({MAX_INPUT_BYTES // (1024 * 1024)} MiB limit)")
        text = _normalize(mdx_content)
        if not text.strip():
            self.warnings.append("Input is empty; wrote a minimal page")

        self.unresolved = []
        self.outside = []
        self.current_file = source_file
        self.page_key = kwargs.get("page_key")
        self.source_rel = kwargs.get("source_rel")
        partial = bool(kwargs.get("partial"))

        fm_lines, body = _split_frontmatter(text)
        if fm_lines is not None:
            fm_lines = self._fold_block_scalars(fm_lines)
            fm_lines = [self._clean_fm_line(ln) for ln in docusaurus.convert_frontmatter(fm_lines)]
        body = docusaurus.unwrap_mdx_code_blocks(body)
        body = self.convert_docusaurus(body)
        body = self.convert_code_blocks(body)
        if partial:
            # A snippet is imported into other pages: no frontmatter and no title of its own.
            for step in (
                self.convert_banner,
                self.convert_api_links,
                lambda b: self.convert_relative_links(b, source_file),
                lambda b: self.handle_images(b, source_file),
                self.convert_lists_with_bold_headers,
                self.convert_tabs,
                self.convert_numbered_steps,
                self.convert_accordions,
                self.convert_callouts,
                self.convert_emoji,
            ):
                body = step(body)
            # Mintlify snippet variables are used bare: {name}, not {props.name}.
            body = re.sub(r"\{props\.(\w+)\}", r"{\1}", body)
            body = _tidy_blank_lines(body)
            return strip_emoji_everywhere(body.strip("\n") + "\n")
        existing = fm_lines or []
        fm_title = _fm_get(existing, "title")
        fm_description = _fm_get(existing, "description")

        title = fm_title or self.extract_title(body)
        if title == "Untitled" and source_file is not None:
            title = self._title_from_path(Path(source_file))
        description = fm_description or self.extract_description(body)
        if description:
            description = re.sub(
                r"^[\u2190-\u2BFF\U0001F000-\U0001FAFF\uFE0F\u200d\s]+", "", description
            )
        body = self.remove_original_title(body, fm_title if fm_title else None)

        body = self.convert_banner(body)
        body = self.convert_api_links(body)
        body = self.convert_relative_links(body, source_file)
        body = self.handle_images(body, source_file)
        body = self.convert_lists_with_bold_headers(body)
        body = self.convert_tabs(body)
        body = self.convert_numbered_steps(body)
        body = self.convert_accordions(body)
        body = self.convert_callouts(body)
        body = self.convert_help_sections(body)
        body = self.convert_option_fields(body)
        body = self.convert_emoji(body)

        if fm_lines is None:
            header = self.create_frontmatter(
                title, description, icon=kwargs.get("icon") or "", mode=kwargs.get("mode") or ""
            )
        else:
            new = []
            if fm_title is None:
                new.append(f"title: {json.dumps(title, ensure_ascii=False)}")
            if fm_description is None and description:
                new.append(f"description: {json.dumps(description, ensure_ascii=False)}")
            tail = []
            for key in ("icon", "mode"):
                if kwargs.get(key) and _fm_get(existing, key) is None:
                    tail.append(f"{key}: {json.dumps(kwargs[key], ensure_ascii=False)}")
            # The title leads the frontmatter, whether it was written or derived.
            lead = [ln for ln in existing if re.match(r"^title\s*:", ln)]
            rest = [ln for ln in existing if ln not in lead]
            new_title = [ln for ln in new if ln.startswith("title:")]
            new_other = [ln for ln in new if not ln.startswith("title:")]
            header = "\n".join(["---", *new_title, *lead, *new_other, *rest, *tail, "---"])

        body = _tidy_blank_lines(body)
        result = strip_emoji_everywhere(header + "\n\n" + body.lstrip("\n"))
        if self.outside:
            shown = ", ".join(self.outside[:3]) + (", ..." if len(self.outside) > 3 else "")
            self.warnings.append(
                f"{len(self.outside)} link(s) climb above the docs folder ({shown}); they are "
                "left as written and will not resolve"
            )
        if self.unresolved:
            shown = ", ".join(self.unresolved[:4]) + (", ..." if len(self.unresolved) > 4 else "")
            self.warnings.append(
                f"{len(self.unresolved)} link(s) match no docs page ({shown}); they point outside "
                "the docs. Pass --site-url to make them absolute"
            )

        if kwargs.get("validate"):
            self.validation_errors = self.validate_mdx(result)
        return result
