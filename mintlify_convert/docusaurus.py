#!/usr/bin/env python3
"""
Docusaurus to Mintlify syntax rewrites.

Every function takes plain text and returns plain text. The ones that read prose expect the
text to have its code already masked (see converter._mask_code), so nothing inside a code
fence or an inline code span is touched. The two code-block helpers work on one block.
"""

import re
import textwrap
from typing import Dict, List, Optional, Set, Tuple

# Components Mintlify provides, so they are never reported as unresolved.
MINTLIFY_COMPONENTS = frozenset(
    {
        "Accordion", "AccordionGroup", "Badge", "Banner", "Callout", "Card", "CardGroup",
        "Check", "CodeGroup", "Color", "Columns", "Danger", "Expandable", "Frame", "Icon",
        "Info", "Latex", "MDX", "Note", "Panel", "ParamField", "Prompt", "RequestExample",
        "ResponseExample", "ResponseField", "Step", "Steps", "Tab", "Tabs", "Tile", "Tiles",
        "Tip", "Tooltip", "Tree", "Update", "View", "Visibility", "Warning", "Mermaid",
    }
)  # fmt: skip

# Admonition type -> Mintlify callout component.
_ADMONITION_TAGS = {
    "note": "Note",
    "tip": "Tip",
    "info": "Info",
    "warning": "Warning",
    "caution": "Warning",
    "danger": "Danger",
    "success": "Check",
    "secondary": "Note",
}

_DROPPED_FRONTMATTER = frozenset(
    {
        "id", "slug", "sidebar_position", "sidebar_class_name", "sidebar_custom_props",
        "pagination_label", "pagination_next", "pagination_prev", "hide_title",
        "hide_table_of_contents", "hide_reading_time", "toc_min_heading_level",
        "toc_max_heading_level", "displayed_sidebar", "custom_edit_url", "draft", "unlisted",
        "tags", "image", "parse_number_prefixes", "last_update", "format",
    }
)  # fmt: skip

_ADM_OPEN = re.compile(
    r"^([ \t]*)(:{3,})[ \t]*([A-Za-z][\w-]*)[ \t]*(?:\[(.*)\])?[ \t]*(?:\{[^{}\n]*\})?[ \t]*(.*?)[ \t]*$"
)
_ADM_CLOSE = re.compile(r"^([ \t]*)(:{3,})[ \t]*$")
_STACK_SCAN = 64


# --- frontmatter -------------------------------------------------------------


def convert_frontmatter(lines: List[str]) -> List[str]:
    """Drop Docusaurus-only keys and rename sidebar_label to Mintlify's sidebarTitle."""
    out: List[str] = []
    dropping = False
    for line in lines:
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:(.*)$", line)
        if m:
            key = m.group(1)
            dropping = key in _DROPPED_FRONTMATTER
            if dropping:
                continue
            if key == "sidebar_label":
                out.append(f"sidebarTitle:{m.group(2)}")
                continue
        elif dropping and (not line.strip() or line[0] in " \t-"):
            continue
        else:
            dropping = False
        out.append(line)
    return out


# --- imports -----------------------------------------------------------------

_IMPORT_RE = re.compile(
    r"""^import\s*(?:(?P<clause>[^'"]*?)\s*from\s*)?(?P<q>['"])(?P<mod>[^'"\n]+)(?P=q)"""
    r"""(?:\s*(?:with|assert)\s*\{[^}\n]*\})?\s*;?\s*$""",
    re.DOTALL,
)


def _import_names(clause: Optional[str]) -> List[str]:
    if not clause:
        return []
    names = []
    for part in re.split(r"[,{}]", clause):
        part = part.strip()
        if not part:
            continue
        part = re.sub(r"^\*\s+as\s+", "", part)
        part = part.split(" as ")[-1].strip()
        if re.fullmatch(r"[A-Za-z_$][\w$]*", part):
            names.append(part)
    return names


def remove_imports(text: str, removed: Dict[str, str], rewrite=None) -> str:
    """Remove ES imports: Mintlify pages cannot import site code, only /snippets files.

    Each removed name is recorded in `removed` (name -> module). `rewrite(module)` may return
    a /snippets/ path for a module that has been converted into a snippet; that import is kept,
    pointing at the snippet.
    """
    lines = text.split("\n")
    out: List[str] = []
    i = 0
    n = len(lines)
    while i < n:
        if not re.match(r"^import[\s'\"{*]", lines[i]):
            out.append(lines[i])
            i += 1
            continue
        stmt = None
        for j in range(i, min(n, i + 20)):
            if re.search(r"""(?:['"]|\})[ \t]*;?[ \t]*$""", lines[j]):
                stmt = "\n".join(lines[i : j + 1])
                end = j
                break
        m = _IMPORT_RE.match(stmt) if stmt else None
        if not m or m.group("mod").startswith(("/snippets/", "@/snippets/")):
            out.append(lines[i])
            i += 1
            continue
        new_mod = rewrite(m.group("mod")) if rewrite else None
        if new_mod and m.group("clause"):
            out.append(f'import {m.group("clause").strip()} from "{new_mod}";')
            i = end + 1
            continue
        for name in _import_names(m.group("clause")):
            removed[name] = m.group("mod")
        i = end + 1
    if len(out) == n and out == lines:
        return text
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out))


def unknown_components(text: str) -> List[str]:
    """Capitalised JSX tags that are neither Mintlify components nor defined in the page."""
    defined = set(re.findall(r"\b(?:const|function|class|let|var)\s+([A-Z]\w*)", text))
    for m in re.finditer(r"""^import\s+([^'"\n]+?)\s+from\s+['"]""", text, re.MULTILINE):
        defined.update(_import_names(m.group(1)))
    found: List[str] = []
    for m in re.finditer(r"<([A-Z][A-Za-z0-9]*)\b", text):
        name = m.group(1)
        if name not in MINTLIFY_COMPONENTS and name not in defined and name not in found:
            found.append(name)
    return found


_CODE_BLOCK_OPEN = re.compile(r"^([ \t]*)(`{3,}|~{3,})[ \t]*mdx-code-block\b.*$")


def unwrap_mdx_code_blocks(text: str) -> str:
    """Docusaurus writes real JSX inside ```mdx-code-block fences (often to open a <Tabs> around
    ordinary fences). Mintlify has no such fence, so the contents become plain MDX."""
    lines = text.split("\n")
    out: List[str] = []
    i, n = 0, len(lines)
    while i < n:
        m = _CODE_BLOCK_OPEN.match(lines[i])
        if not m:
            other = re.match(r"^[ \t]*(`{3,}|~{3,})", lines[i])
            if other:
                # An ordinary fence (it may quote an mdx-code-block example): copy it whole.
                closer = re.compile(
                    r"^[ \t]*" + re.escape(other.group(1)[0]) + "{%d,}[ \t]*$" % len(other.group(1))
                )
                k = i + 1
                while k < n and not closer.match(lines[k]):
                    k += 1
                out.extend(lines[i : k + 1])
                i = k + 1
                continue
            out.append(lines[i])
            i += 1
            continue
        indent, fence = m.group(1), m.group(2)
        close = re.compile(r"^[ \t]*" + re.escape(fence[0]) + "{%d,}[ \t]*$" % len(fence))
        j = i + 1
        while j < n and not close.match(lines[j]):
            j += 1
        if j >= n:  # unclosed: leave it for the fence handling
            out.extend(lines[i:])
            break
        inner = lines[i + 1 : j]
        out.extend(ln[len(indent) :] if ln.startswith(indent) else ln for ln in inner)
        i = j + 1
    return "\n".join(out)


def convert_embeds(text: str) -> str:
    """<LiteYouTubeEmbed id="..."/> as a responsive iframe (Mintlify allows iframes)."""

    def youtube(m):
        attrs = parse_attrs(m.group(1))
        vid = attrs.get("id")
        if not vid or not re.fullmatch(r"[\w-]{6,20}", vid):
            return m.group(0)
        title = _quote(attrs.get("title") or "Video")
        return (
            f'<iframe className="w-full aspect-video rounded-xl" '
            f'src="https://www.youtube.com/embed/{vid}" title="{title}" frameBorder="0" '
            f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; '
            f'picture-in-picture" allowFullScreen></iframe>'
        )

    text = re.sub(r"<LiteYouTubeEmbed\b([^<>]{0,1500}?)/>", youtube, text, flags=re.DOTALL)
    # The wrapper div only styled the Docusaurus player.
    return re.sub(
        r'<div className="video-container">\s*(<iframe\b.*?</iframe>)\s*</div>',
        r"\1",
        text,
        flags=re.DOTALL,
    )


_JS_STRING = re.compile(
    r"""'((?:[^'\\\n]|\\.)*)'|"((?:[^"\\\n]|\\.)*)"|`((?:[^`\\$]|\\.|\$(?!\{))*)`""", re.DOTALL
)
_JS_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"', "`": "`", "$": "$"}


def _js_literal(expr: str) -> Optional[str]:
    """The value of a JS expression made only of string literals joined with +, else None."""
    pos, parts = 0, []
    expr = expr.strip()
    while pos < len(expr):
        m = _JS_STRING.match(expr, pos)
        if not m:
            return None
        raw = next(g for g in m.groups() if g is not None)
        parts.append(
            re.sub(
                r"\\(u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)",
                lambda e: (
                    chr(int(e.group(1)[1:], 16))
                    if e.group(1)[0] in "ux" and len(e.group(1)) > 1
                    else _JS_ESCAPES.get(e.group(1), e.group(1))
                ),
                raw,
            )
        )
        pos = m.end()
        gap = re.match(r"\s*(?:\+\s*)?", expr[pos:])
        if gap is None:
            return None
        pos += gap.end()
    return "".join(parts) if parts else None


def convert_code_components(text: str, restore=None, stash=None) -> str:
    """<CodeBlock language="md" title="t">{'literal text'}</CodeBlock> to a fenced block.

    Only literal strings can be converted; code that is computed at build time is left for
    neutralize_unknown_components.
    """

    def sub(m):
        attrs = parse_attrs(m.group(2))
        value = _js_literal(restore(m.group(3)) if restore else m.group(3))
        if value is None:
            return m.group(0)
        lang = _expr_string(attrs.get("language", "")) or attrs.get("language", "")
        if not lang:
            lm = re.search(r"language-([\w+#-]+)", attrs.get("className", ""))
            lang = lm.group(1) if lm else ""
        title = _expr_string(attrs.get("title", "")) or attrs.get("title", "")
        longest = max((len(r) for r in re.findall(r"`+", value)), default=0)
        fence = "`" * max(3, longest + 1)
        info = lang + (f' title="{_quote(title)}"' if title and not title.startswith("{") else "")
        block = f"{fence}{info}\n{value.strip(chr(10))}\n{fence}"
        return stash(block) if stash else block

    return re.sub(
        r"<(Code|CodeBlock)\b([^<>]{0,400}?)>\s*\{(.{0,6000}?)\}\s*</\1>",
        sub,
        text,
        flags=re.DOTALL,
    )


_ADMONITION_COMPONENT = re.compile(r"<Admonition\b([^<>]{0,600}?)>(.*?)</Admonition>", re.DOTALL)


def convert_admonition_components(text: str) -> str:
    """<Admonition type="tip" title="T"> children </Admonition> to the matching callout."""

    def sub(m):
        attrs = parse_attrs(m.group(1))
        kind = (_expr_string(attrs.get("type", "")) or attrs.get("type", "note")).lower()
        tag = _ADMONITION_TAGS.get(kind, "Note")
        title = _expr_string(attrs.get("title", "")) or attrs.get("title", "")
        body = textwrap.dedent(m.group(2)).strip("\n")
        head = f"**{title}**\n\n" if title else ""
        return f"<{tag}>\n\n{head}{body}\n\n</{tag}>"

    return _ADMONITION_COMPONENT.sub(sub, text)


_IMAGE_MODULE = re.compile(r"\.(?:png|jpe?g|gif|svg|webp)$", re.IGNORECASE)


def convert_image_components(text: str, removed: Dict[str, str]) -> str:
    """`import Logo from './logo.svg'` then `<Logo />` becomes an <img> of that file."""
    for name, mod in removed.items():
        if not _IMAGE_MODULE.search(mod):
            continue

        def sub(m, name=name, mod=mod):
            attrs = parse_attrs(m.group(1))
            alt = _expr_string(attrs.get("title", "")) or attrs.get("title") or attrs.get("alt")
            alt = alt if alt and not alt.startswith("{") else name
            return f'<img src="{_quote(mod)}" alt="{_quote(alt)}" />'

        text = re.sub(rf"<{re.escape(name)}\b([^<>]{{0,400}}?)/>", sub, text)
    return text


_RUNTIME_HOOKS = re.compile(
    r"\buse(?:Location|ActiveDocContext|BaseUrl|DocusaurusContext|ColorMode|History|"
    r"IsBrowser|GlobalData|PluginData)\b"
)


def drop_runtime_exports(text: str, warnings: List[str]) -> str:
    """`export const X = () => ...` that calls a Docusaurus hook cannot run on Mintlify.

    The export is removed and, with it, the component it defined (neutralised later)."""
    lines = text.split("\n")
    out: List[str] = []
    i, n, dropped = 0, len(lines), []
    while i < n:
        if not re.match(r"^export\s+(?:const|function|default)\b", lines[i]):
            out.append(lines[i])
            i += 1
            continue
        j, depth = i, 0
        while j < n:
            depth += (
                lines[j].count("{")
                + lines[j].count("(")
                - lines[j].count("}")
                - lines[j].count(")")
            )
            j += 1
            if depth <= 0 and (j >= n or not lines[j].strip() or not lines[j][0].isspace()):
                break
        block = "\n".join(lines[i:j])
        if _RUNTIME_HOOKS.search(block):
            name = re.match(r"^export\s+(?:const|function)\s+(\w+)", block)
            dropped.append(name.group(1) if name else "export")
            out.append(
                f"{{/* TODO(mintlify-convert): export {dropped[-1]} uses Docusaurus hooks */}}"
            )
        else:
            out.extend(lines[i:j])
        i = j
    if dropped:
        warnings.append(
            f"Removed export(s) {', '.join(dropped)}: they call Docusaurus hooks that do not exist on Mintlify"
        )
    return "\n".join(out)


def convert_require_links(text: str) -> str:
    """<a href={require('./f.docx')}>{'Text'}</a> to a Markdown link (so the file is copied)."""
    return re.sub(
        r"""<a\b[^<>]*?\bhref=\{\s*require\(\s*(['"])([^'"]+)\1\s*\)\s*\}[^<>]*>\s*\{?\s*(?:'([^'\n]*)'|"([^"\n]*)")?\s*\}?\s*</a>""",
        lambda m: f"[{m.group(3) or m.group(4) or 'Download'}]({m.group(2)})",
        text,
    )


def normalize_img_sources(text: str) -> str:
    """src={require('x.png')} and src={useBaseUrl('/img/x.png')} to a plain src="..." string."""
    return re.sub(
        r"""(<img\b[^<>]*?\bsrc=)\{\s*(?:require|useBaseUrl)\(\s*(['"])([^'"]+)\2\s*\)\s*\}""",
        lambda m: f'{m.group(1)}"{m.group(3)}"',
        text,
        flags=re.DOTALL,
    )


def _tag_end(text: str, start: int) -> int:
    """Index just past the '>' that closes the tag opened at `start`, or -1."""
    depth, quote, i, n = 0, "", start, len(text)
    while i < n and i - start < 4000:
        ch = text[i]
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'" and depth == 0:
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == ">" and depth == 0:
            return i + 1
        i += 1
    return -1


def _drop_expressions(text: str) -> str:
    """Remove balanced {js expressions} from JSX children, keeping the plain content around."""
    out, depth = [], 0
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
        elif not depth:
            out.append(ch)
    return "".join(out)


def neutralize_unknown_components(
    text: str, warnings: List[str], removed: Optional[Dict[str, str]] = None
) -> str:
    """Replace components Mintlify cannot render with a TODO comment.

    Mintlify fails the page when an MDX component is undefined, so a left-over <Foo /> would
    break the whole page. A component whose children are plain content keeps its children;
    one that computes its output with JavaScript is dropped.
    """
    names = unknown_components(text)
    for name in names:
        origin = (removed or {}).get(name)
        count = 0
        pos = 0
        while True:
            m = re.compile(rf"<{re.escape(name)}\b").search(text, pos)
            if not m:
                break
            end = _tag_end(text, m.end())
            if end == -1:
                pos = m.end()
                continue
            count += 1
            opening = text[m.start() : end]
            note = f"{{/* TODO(mintlify-convert): {name} component has no Mintlify equivalent */}}"
            if opening.endswith("/>"):
                text = text[: m.start()] + note + text[end:]
                pos = m.start() + len(note)
                continue
            close = text.find(f"</{name}>", end)
            if close == -1:
                text = text[: m.start()] + note + text[end:]
                pos = m.start() + len(note)
                continue
            children = _drop_expressions(text[end:close])
            replacement = note + children
            text = text[: m.start()] + replacement + text[close + len(name) + 3 :]
            pos = m.start() + len(replacement)
        suffix = f" (imported from '{origin}')" if origin else ""
        warnings.append(
            f"<{name}>{suffix} has no Mintlify equivalent; replaced {count} use(s) with a "
            "TODO comment"
        )
    return text


# --- headings and comments ---------------------------------------------------

_HEADING_ID_RE = re.compile(
    r"^(#{1,6}[ \t]+.*?)[ \t]*(?:\{/\*[ \t]*#([\w-]+)[ \t]*\*/\}|\{#([\w-]+)\})[ \t]*$"
)


def _slug(text: str) -> str:
    text = re.sub(r"[`*_]", "", text).lower()
    return re.sub(r"[\s_]+", "-", re.sub(r"[^\w\s-]", "", text)).strip("-")


def heading_anchors(text: str) -> Dict[str, str]:
    """{custom id: anchor Mintlify generates} for headings whose '{#id}' differs from their slug."""
    found: Dict[str, str] = {}
    for line in text.split("\n"):
        m = _HEADING_ID_RE.match(line)
        if m:
            custom = m.group(2) or m.group(3)
            slug = _slug(m.group(1).lstrip("#").strip())
            if slug and slug != custom:
                found[custom] = slug
    return found


def strip_heading_ids(text: str, warnings: Optional[List[str]]) -> str:
    """Remove '{#id}' and '{/* #id */}' heading ids; MDX would read '{#id}' as JavaScript.

    One warning lists the ids whose anchor Mintlify will generate differently.
    """
    changed: List[str] = []

    def sub(m):
        custom = m.group(2) or m.group(3)
        if _slug(m.group(1).lstrip("#").strip()) != custom:
            changed.append("#" + custom)
        return m.group(1)

    result = "\n".join(_HEADING_ID_RE.sub(sub, ln) for ln in text.split("\n"))
    if changed and warnings is not None:
        shown = ", ".join(changed[:3]) + (", ..." if len(changed) > 3 else "")
        warnings.append(
            f"{len(changed)} custom heading id(s) dropped ({shown}); links to them may break "
            "because Mintlify generates its own anchors"
        )
    return result


def convert_html_comments(text: str) -> str:
    """<!-- x --> is invalid in MDX; write it as a {/* x */} comment."""
    return re.sub(
        r"<!--(.{0,5000}?)-->",
        lambda m: "{/*" + m.group(1).replace("*/", "* /") + "*/}",
        text,
        flags=re.DOTALL,
    )


# --- Docusaurus components ---------------------------------------------------


_THEMED_FRAME = (
    "<Frame>\n"
    '  <img className="block dark:hidden" src="{light}" alt="{alt}" />\n'
    '  <img className="hidden dark:block" src="{dark}" alt="{alt}" />\n'
    "</Frame>"
)
_GH_IMG = r"!\[([^\]\n]*)\]\(([^)\s#]+)#gh-(light|dark)-mode-only\)"


def _themed_frame(light: str, dark: str, alt: str, dark_alt: Optional[str] = None) -> str:
    frame = _THEMED_FRAME.format(
        light=_quote(light), dark=_quote(dark), alt=_quote(alt or "Documentation image")
    )
    if dark_alt and dark_alt != alt:
        head, tail = frame.rsplit('alt="', 1)
        frame = head + 'alt="' + _quote(dark_alt) + tail[tail.index('"') :]
    return frame


def _own_lines(text: str, start: int, end: int, replacement: str) -> str:
    """Put a block-level replacement on lines of its own when text surrounds it."""
    line_start = text.rfind("\n", 0, start) + 1
    before = text[line_start:start].strip()
    nl = text.find("\n", end)
    after = text[end : nl if nl != -1 else len(text)].strip()
    if before:
        # Inside a list item the block stays part of the item, so it is indented under it.
        item = re.match(r"([ \t]*)(?:\d+[.)]|[-*+])[ \t]+", text[line_start:start])
        if item:
            pad = " " * len(item.group(0))
            replacement = "\n".join(pad + ln for ln in replacement.split("\n"))
    return ("\n" if before else "") + replacement + ("\n" if after else "")


def convert_themed_images(text: str, warnings: List[str]) -> str:
    """<ThemedImage sources> and GitHub-style #gh-*-mode-only images to a light/dark Frame."""

    def themed(m):
        attrs = parse_attrs(m.group(1))
        sources = attrs.get("sources", "")
        found = {}
        for mode in ("light", "dark"):
            s = re.search(
                rf"\b{mode}\s*:\s*(?:useBaseUrl|require)?\(?\s*['\"]([^'\"]+)['\"]", sources
            )
            if s:
                found[mode] = s.group(1)
        if len(found) != 2:
            warnings.append("<ThemedImage> sources could not be read; left as written")
            return m.group(0)
        return _themed_frame(
            found["light"],
            found["dark"],
            _expr_string(attrs.get("alt", "")) or attrs.get("alt", ""),
        )

    text = re.sub(r"<ThemedImage\b([^<>]{0,1500}?)/>", themed, text, flags=re.DOTALL)

    def pair(m):
        first, second = (m.group(1), m.group(2), m.group(3)), (m.group(4), m.group(5), m.group(6))
        by_mode = {first[2]: first, second[2]: second}
        if len(by_mode) != 2:
            return m.group(0)
        return _own_lines(
            m.string,
            m.start(),
            m.end(),
            _themed_frame(
                by_mode["light"][1], by_mode["dark"][1], by_mode["light"][0], by_mode["dark"][0]
            ),
        )

    text = re.sub(_GH_IMG + r"[ \t]*\n?[ \t]*" + _GH_IMG, pair, text)

    def single(m):
        cls = "block dark:hidden" if m.group(3) == "light" else "hidden dark:block"
        return f'<img className="{cls}" src="{_quote(m.group(2))}" alt="{_quote(m.group(1) or "Documentation image")}" />'

    return re.sub(_GH_IMG, single, text)


def unwrap_components(text: str, names=("BrowserWindow", "Zoom", "APITable")) -> str:
    """Drop presentation-only wrappers (browser chrome, click-to-zoom); Mintlify zooms images."""
    for name in names:
        text = re.sub(rf"^[ \t]*<{name}\b[^<>]*?>[ \t]*\n?", "", text, flags=re.MULTILINE)
        text = re.sub(rf"<{name}\b[^<>]*?>", "", text)
        text = re.sub(rf"^[ \t]*</{name}>[ \t]*\n?", "", text, flags=re.MULTILINE)
        text = text.replace(f"</{name}>", "")
    return re.sub(r"\n{3,}", "\n\n", text)


def convert_inline_components(
    text: str,
    warnings: List[str],
    page_url: Optional[str] = None,
    source_path: Optional[str] = None,
    doc_cards: Optional[str] = None,
) -> str:
    """<Translate>, <Link>, <URLPath>/<FilePath>, <IframeWindow> and the auto-generated TOC and
    card lists. `doc_cards` is the replacement for <DocCardList />."""
    text = re.sub(r"<Translate\b[^>\n]{0,500}?(?<!/)>([^<\n]{0,1000})</Translate>", r"\1", text)

    def link(m):
        attrs = parse_attrs(m.group(1))
        target = attrs.get("to") or attrs.get("href")
        return f"[{m.group(2)}]({target})" if target else m.group(0)

    text = re.sub(r"<Link\b([^>\n]{0,500}?)>([^<\n]{1,1000})</Link>", link, text)
    for tag, value in (("URLPath", page_url), ("FilePath", source_path)):
        if value:
            text = re.sub(rf"<{tag}\s*/>", f"`{value}`", text)
    if re.search(r"<IframeWindow\b", text):
        text = re.sub(
            r"^[ \t]*<IframeWindow\b[^<>]{0,500}/>[ \t]*\n?", "", text, flags=re.MULTILINE
        )
        warnings.append("Removed <IframeWindow>; live site previews have no Mintlify equivalent")
    text = convert_themed_images(text, warnings)
    text = convert_embeds(text)
    text = unwrap_components(text)
    pattern = r"^[ \t]*<DocCardList\b[^>\n]{0,500}/>[ \t]*\n?"
    if re.search(pattern, text, re.MULTILINE):
        text = re.sub(
            pattern, lambda _m: (doc_cards + "\n") if doc_cards else "", text, flags=re.MULTILINE
        )
        if not doc_cards:
            warnings.append("Removed <DocCardList>; Mintlify builds its own navigation")
    pattern = r"^[ \t]*<TOCInline\b[^>\n]{0,500}/>[ \t]*\n?"
    if re.search(pattern, text, re.MULTILINE):
        text = re.sub(pattern, "", text, flags=re.MULTILINE)
        warnings.append("Removed <TOCInline>; Mintlify builds its own contents and navigation")
    return text


def parse_attrs(raw: str) -> Dict[str, str]:
    """Parse JSX attributes. Values: "x" and 'x' give x, {expr} gives the raw expression
    wrapped in braces, a bare attribute gives 'true'."""
    attrs: Dict[str, str] = {}
    i, n = 0, len(raw)
    while i < n:
        m = re.compile(r"\s*([A-Za-z_][\w-]*)").match(raw, i)
        if not m:
            break
        name, i = m.group(1), m.end()
        if i < n and raw[i] == "=":
            i += 1
            if i < n and raw[i] in "\"'":
                end = raw.find(raw[i], i + 1)
                if end == -1:
                    break
                attrs[name] = raw[i + 1 : end]
                i = end + 1
            elif i < n and raw[i] == "{":
                depth, j = 0, i
                while j < n:
                    depth += {"{": 1, "}": -1}.get(raw[j], 0)
                    j += 1
                    if depth == 0:
                        break
                attrs[name] = raw[i:j]
                i = j
            else:
                break
        else:
            attrs[name] = "true"
    return attrs


def _quote(value: str) -> str:
    return value.replace('"', "&quot;")


def _expr_string(value: str) -> Optional[str]:
    """'x' from {'x'} or {"x"}, else None."""
    m = re.fullmatch(r"""\{\s*(['"`])([^'"`]*)\1\s*\}""", value.strip())
    return m.group(2) if m else None


_TAG_RE = re.compile(r"<(/?)(Tabs|TabItem)\b([^>]{0,2000}?)(/?)>")


def convert_tabs(text: str) -> str:
    """<Tabs>/<TabItem value label default> to Mintlify <Tabs>/<Tab title>."""
    pieces: List[str] = []
    stack: List[dict] = []
    last = 0
    for m in _TAG_RE.finditer(text):
        pieces.append(text[last : m.start()])
        last = m.end()
        closing, name, raw, selfclose = m.group(1), m.group(2), m.group(3), m.group(4)
        if name == "Tabs":
            if closing:
                if stack:
                    frame = stack.pop()
                    idx = frame["default"]
                    if idx is None and frame["default_value"] is not None:
                        idx = (
                            frame["values"].index(frame["default_value"])
                            if (frame["default_value"] in frame["values"])
                            else None
                        )
                    if idx:
                        pieces[frame["slot"]] = _tabs_open(frame["attrs"], idx)
                pieces.append("</Tabs>")
                continue
            attrs = parse_attrs(raw)
            labels = {}
            for obj in re.findall(r"\{[^{}]*\}", attrs.get("values", "")):
                lab = re.search(r"label\s*:\s*(['\"`])(.*?)\1", obj)
                val = re.search(r"value\s*:\s*(['\"`])(.*?)\1", obj)
                if lab and val:
                    labels[val.group(2)] = lab.group(2)
            default_value = attrs.get("defaultValue")
            if default_value is not None and default_value.startswith("{"):
                default_value = _expr_string(default_value)
            frame = {
                "attrs": attrs,
                "labels": labels,
                "values": [],
                "default": None,
                "default_value": default_value,
                "slot": len(pieces),
            }
            pieces.append(_tabs_open(attrs, None))
            if selfclose:
                pieces[-1] = pieces[-1][:-1] + " />"
            else:
                stack.append(frame)
            continue
        # TabItem
        if closing:
            pieces.append("</Tab>")
            continue
        attrs = parse_attrs(raw)
        frame = stack[-1] if stack else None
        value = attrs.get("value", "")
        if value.startswith("{"):
            value = _expr_string(value) or ""
        label = attrs.get("label")
        if label is not None and label.startswith("{"):
            label = _expr_string(label)
        title = label or (frame["labels"].get(value) if frame else None) or value
        if not title:
            title = f"Tab {len(frame['values']) + 1}" if frame else "Tab"
        if frame is not None:
            frame["values"].append(value or title)
            if attrs.get("default") in ("true", "{true}") and frame["default"] is None:
                frame["default"] = len(frame["values"]) - 1
        pieces.append(f'<Tab title="{_quote(title)}">')
    pieces.append(text[last:])
    return "".join(pieces)


def _tabs_open(attrs: Dict[str, str], default_index: Optional[int]) -> str:
    kept = {
        k: v
        for k, v in attrs.items()
        if k not in {"groupId", "queryString", "values", "defaultValue", "lazy"}
    }
    if default_index:
        kept["defaultTabIndex"] = "{%d}" % default_index
    if not kept:
        return "<Tabs>"
    parts = []
    for k, v in kept.items():
        if v == "true":
            parts.append(k)
        elif v.startswith("{"):
            parts.append(f"{k}={v}")
        else:
            parts.append(f'{k}="{_quote(v)}"')
    return "<Tabs " + " ".join(parts) + ">"


def convert_details(text: str) -> str:
    """<details><summary>T</summary> to <Accordion title="T">."""

    def opener(m):
        attrs = parse_attrs(m.group(1))
        summary = m.group(2)
        if summary is None:
            title = "Details"
        else:
            title = re.sub(r"</?code>", "`", summary)
            title = re.sub(r"<[^>]+>", "", title)
            title = re.sub(r"\s+", " ", title).strip() or "Details"
        extra = " defaultOpen" if "open" in attrs else ""
        # Mintlify gives an Accordion no anchor of its own, so keep the id for links to it.
        anchor = f'<div id="{_quote(attrs["id"])}" />\n\n' if attrs.get("id") else ""
        return f'{anchor}<Accordion title="{_quote(title)}"{extra}>\n\n'

    text = re.sub(
        r"<details\b([^>]{0,1000})>(?:\s*<summary>(.{0,1000}?)</summary>)?[ \t]*\n?(?:[ \t]*\n)?",
        opener,
        text,
        flags=re.DOTALL,
    )
    return re.sub(r"</details>", "</Accordion>", text)


def convert_admonitions(text: str, warnings: List[str]) -> str:
    """:::type[Title] ... ::: blocks (any colon count, nested) to Mintlify callouts."""
    lines = text.split("\n")
    stack: List[Tuple[int, int]] = []
    pairs: Dict[int, int] = {}
    for i, line in enumerate(lines):
        if len(line) > 2000:
            continue
        close = _ADM_CLOSE.match(line)
        if close:
            count = len(close.group(2))
            for k in range(len(stack) - 1, max(-1, len(stack) - 1 - _STACK_SCAN), -1):
                if stack[k][1] == count:
                    pairs[stack[k][0]] = i
                    del stack[k:]
                    break
            continue
        opened = _ADM_OPEN.match(line)
        if opened:
            stack.append((i, len(opened.group(2))))
    if not pairs:
        return text

    closers: Dict[int, Tuple[str, str]] = {}
    out: List[str] = []
    drop_blank = False
    for i, line in enumerate(lines):
        if i in pairs:
            m = _ADM_OPEN.match(line)
            assert m is not None
            indent, kind = m.group(1), m.group(3).lower()
            title = (m.group(4) if m.group(4) is not None else m.group(5)).strip()
            if kind not in _ADMONITION_TAGS:
                warnings.append(f"Unknown admonition type ':::{kind}' converted to <Note>")
            tag = _ADMONITION_TAGS.get(kind, "Note")
            closers[pairs[i]] = (indent, tag)
            out.append(f"{indent}<{tag}>")
            out.append("")
            if title:
                out.append(f"{indent}{title if '**' in title else '**' + title + '**'}")
                out.append("")
            drop_blank = True
        elif i in closers:
            indent, tag = closers[i]
            while out and not out[-1].strip():
                out.pop()
            out.extend(["", f"{indent}</{tag}>"])
            drop_blank = False
        else:
            if drop_blank and not line.strip():
                continue
            drop_blank = False
            out.append(line)
    return "\n".join(out)


# --- code blocks -------------------------------------------------------------

_FENCE_LINE_RE = re.compile(r"^(`{3,}|~{3,})(.*)$")
_MAGIC_RE = re.compile(
    r"^[ \t]*(?:(?://|#|--|;|%)[ \t]*|/\*[ \t]*|\{/\*[ \t]*|<!--[ \t]*)"
    r"highlight-(next-line|start|end)[ \t]*(?:\*/\}|\*/|-->)?[ \t]*$"
)
_META_RE = re.compile(
    r"""(?P<key>title|icon|highlight|focus)=(?P<val>"[^"]*"|'[^']*'|\{[^}]*\})"""
    r"""|(?P<bare>\{[\d,\s-]+\})|(?P<flag>\S+)"""
)


def _parse_lines(spec: str) -> Set[int]:
    result: Set[int] = set()
    for part in spec.strip("{} ").split(","):
        part = part.strip()
        if re.fullmatch(r"\d+", part):
            result.add(int(part))
        elif re.fullmatch(r"\d+\s*-\s*\d+", part):
            lo, hi = (int(x) for x in re.split(r"\s*-\s*", part))
            result.update(range(lo, min(hi, lo + 5000) + 1))
    return result


def _format_lines(numbers: Set[int]) -> str:
    out, run = [], []
    for n in sorted(numbers):
        if run and n == run[-1] + 1:
            run.append(n)
            continue
        if run:
            out.append(run)
        run = [n]
    if run:
        out.append(run)
    return ",".join(str(r[0]) if len(r) == 1 else f"{r[0]}-{r[-1]}" for r in out)


_NPM_LINE = re.compile(r"^(\s*(?:\$\s+)?)(npm|npx)\b(.*)$")


def _npm_to(manager: str, line: str) -> str:
    """A command line in yarn or pnpm form; each command of an `a && b` chain is converted."""
    parts = re.split(r"(\s*(?:&&|\|\||;)\s*)", line)
    if len(parts) > 1:
        return "".join(
            (
                p
                if i % 2
                else (
                    _npm_to(manager, ("" if i == 0 else " ") + p).lstrip()
                    if i
                    else _npm_to(manager, p)
                )
            )
            for i, p in enumerate(parts)
        )
    return _npm_one(manager, line)


def _npm_one(manager: str, line: str) -> str:
    m = _NPM_LINE.match(line)
    if not m:
        return line
    indent, tool, rest = m.groups()
    rest = rest.strip()
    if tool == "npx":
        return f"{indent}{manager} dlx {rest}".rstrip()
    sub = re.match(
        r"(install|i|add|uninstall|remove|rm|run|run-script|init|create|ci|test|start)\b\s*(.*)$",
        rest,
    )
    if not sub:
        return line
    verb, args = sub.groups()
    args = re.sub(r"\s*--save(?!-)\b", "", args)
    args = args.replace("--save-dev", "-D").strip()
    is_global = bool(re.search(r"(^|\s)(-g|--global)(\s|$)", args))
    if is_global:
        args = re.sub(r"(^|\s)(-g|--global)(?=\s|$)", " ", args).strip()
        if verb in ("install", "i", "add"):
            return f"{indent}{'yarn global add' if manager == 'yarn' else 'pnpm add -g'} {args}".rstrip()
        if verb in ("uninstall", "remove", "rm"):
            return f"{indent}{'yarn global remove' if manager == 'yarn' else 'pnpm remove -g'} {args}".rstrip()
    if verb in ("install", "i", "add"):
        if not args:
            return f"{indent}{'yarn' if manager == 'yarn' else 'pnpm install'}"
        return f"{indent}{manager} add {args}"
    if verb in ("uninstall", "remove", "rm"):
        return f"{indent}{manager} remove {args}".rstrip()
    if verb in ("run", "run-script"):
        args = re.sub(r"^(\S+)\s+--\s*", r"\1 ", args)
        return f"{indent}{manager} {'' if manager == 'yarn' else 'run '}{args}".replace(
            "  ", " "
        ).rstrip()
    if verb in ("init", "create"):
        return f"{indent}{manager} create {args}".rstrip()
    if verb == "ci":
        return f"{indent}{'yarn install --frozen-lockfile' if manager == 'yarn' else 'pnpm install --frozen-lockfile'}"
    return f"{indent}{manager} {verb} {args}".rstrip()


def convert_npm2yarn(block: str) -> Optional[str]:
    """A fence tagged `npm2yarn` as a CodeGroup with npm, yarn and pnpm tabs, else None."""
    lines = block.split("\n")
    m = _FENCE_LINE_RE.match(lines[0])
    if not m or len(lines) < 2 or not re.search(r"(?:^|\s)npm2yarn\b", m.group(2)):
        return None
    lang = (re.match(r"^([A-Za-z0-9_+#.-]*)", m.group(2).strip()) or [""]).group(1) or "bash"
    if lang == "npm2yarn":
        lang = "bash"
    body = lines[1:-1]
    fence = m.group(1)
    # The block came out of a list item or callout; every line after the first keeps its indent.
    indent = re.match(r"[ \t]*", lines[-1]).group(0)
    label_suffix = ""
    out = ["<CodeGroup>"]
    for name, convert in (("npm", None), ("yarn", "yarn"), ("pnpm", "pnpm")):
        out.append(f"{indent}{fence}{lang} {name}{label_suffix}")
        if convert is None:
            out.extend(body)
        else:
            out.extend(
                (
                    ln[: len(indent)] + _npm_to(convert, ln[len(indent) :])
                    if ln.startswith(indent)
                    else ln
                )
                for ln in body
            )
        out.append(f"{indent}{fence}")
    out.append(f"{indent}</CodeGroup>")
    return "\n".join(out)


def convert_fence(block: str) -> str:
    """Rewrite one fenced block's options and magic comments the Mintlify way.

    `showLineNumbers` becomes `lines`, `{1,3-5}` becomes `highlight={1,3-5}`, and
    `// highlight-next-line` / `highlight-start` / `highlight-end` comments are removed
    and turned into highlighted line numbers. Blocks needing no change come back as is.
    """
    grouped = convert_npm2yarn(block)
    if grouped is not None:
        return grouped
    lines = block.split("\n")
    m = _FENCE_LINE_RE.match(lines[0])
    if not m or len(lines) < 2:
        return block
    fence, info = m.group(1), m.group(2).strip()
    if len(info) > 1000:
        return block
    lang_m = re.match(r"^([A-Za-z0-9_+#.-]*)", info)
    lang = lang_m.group(1) if lang_m else ""
    rest = info[len(lang) :]

    title = None
    show_lines = False
    highlight: Set[int] = set()
    others: List[str] = []
    changed = False
    for t in _META_RE.finditer(rest):
        if t.group("key"):
            key, val = t.group("key"), t.group("val")
            if key == "title":
                inner = val[1:-1]
                if val[0] == '"':
                    title = inner
                elif val[0] == "'" and '"' not in inner:
                    title = inner
                    changed = True
                else:
                    others.append(f"{key}={val}")
            elif key == "highlight":
                highlight |= _parse_lines(val)
            else:
                others.append(f"{key}={val}")
        elif t.group("bare"):
            highlight |= _parse_lines(t.group("bare"))
            changed = True
        else:
            flag = t.group("flag")
            if flag == "showLineNumbers":
                show_lines = True
                changed = True
            elif flag == "lines":
                show_lines = True
            elif flag in ("live", "reference", "noInline"):
                changed = True
            else:
                others.append(flag)
    if not lang and rest.strip():
        changed = True

    body = lines[1:-1]
    kept: List[str] = []
    start: Optional[int] = None
    pending_next = False
    magic_lines: Set[int] = set()
    for ln in body:
        mm = _MAGIC_RE.match(ln)
        if mm:
            changed = True
            kind = mm.group(1)
            if kind == "next-line":
                pending_next = True
            elif kind == "start":
                start = len(kept) + 1
            elif start is not None:
                magic_lines.update(range(start, len(kept) + 1))
                start = None
            continue
        kept.append(ln)
        if pending_next:
            magic_lines.add(len(kept))
            pending_next = False
    if start is not None:
        magic_lines.update(range(start, len(kept) + 1))
    highlight |= magic_lines

    if not changed:
        return block
    options: List[str] = []
    if title is not None:
        options.append(f'title="{title}"')
    if show_lines:
        options.append("lines")
    if highlight:
        options.append("highlight={" + _format_lines(highlight) + "}")
    options.extend(others)
    head = fence + (lang or ("text" if options else ""))
    if options:
        head += " " + " ".join(options)
    return "\n".join([head, *kept, lines[-1]])
