#!/usr/bin/env python3
"""
Mintlify icon names.

The tool pins ``icons.library`` to ``lucide`` in docs.json, so every icon it writes must be a
Lucide name. Names from other sets (Font Awesome, Feather, older Lucide releases) are mapped
to their Lucide equivalent; anything unknown is dropped rather than written as a broken icon.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

ICON_LIBRARY = "lucide"

# Names that are common in other icon sets or that Lucide has renamed.
_ALIASES = {
    "help-circle": "circle-help",
    "question": "circle-help",
    "question-circle": "circle-help",
    "info-circle": "info",
    "check-circle": "circle-check",
    "alert-triangle": "triangle-alert",
    "alert-circle": "circle-alert",
    "exclamation-triangle": "triangle-alert",
    "book": "book-open",
    "docs": "book-open",
    "documentation": "book-open",
    "rocket-launch": "rocket",
    "gear": "settings",
    "cog": "settings",
    "config": "settings",
    "cli": "square-terminal",
    "command-line": "square-terminal",
    "support": "headphones",
    "community": "users",
    "comments": "messages-square",
    "arrow-up-circle": "circle-arrow-up",
    "upgrade": "circle-arrow-up",
    "i18n": "languages",
    "translate": "languages",
    "cloud-arrow-up": "cloud-upload",
    "wand-magic-sparkles": "wand-sparkles",
    "tools": "wrench",
    "sitemap": "network",
    "paint-brush": "palette",
    "theme": "palette",
    "plugin": "plug",
    "api": "square-terminal",
}


@lru_cache(maxsize=1)
def _lucide_names() -> frozenset:
    path = Path(__file__).with_name("lucide_icons.txt")
    try:
        return frozenset(
            line.strip() for line in path.read_text("utf-8").splitlines() if line.strip()
        )
    except OSError:
        return frozenset()


def is_lucide(name: str) -> bool:
    """True when ``name`` is a Lucide icon (or, if the list is unavailable, a plausible name)."""
    names = _lucide_names()
    return name in names if names else bool(name)


def resolve_icon(name: Optional[str]) -> Optional[str]:
    """Return a valid Lucide icon name for ``name``, or None when there is no match."""
    if not isinstance(name, str):
        return None
    key = name.strip().lower().replace("_", "-").replace(" ", "-")
    if not key:
        return None
    for prefix in ("fa-", "fas-", "far-", "lucide-"):
        if key.startswith(prefix):
            key = key[len(prefix) :]
    key = _ALIASES.get(key, key)
    return key if is_lucide(key) else None


# Emoji that appear in prose, mapped to the Lucide icon that stands in for them. Mintlify draws
# these with <Icon icon="..." /> so they match the theme instead of the platform's emoji font.
_EMOJI_ICONS = {
    "⚡": "zap",
    "💸": "banknote",
    "💰": "banknote",
    "💥": "sparkles",
    "✨": "sparkles",
    "💅": "sparkles",
    "🧐": "search",
    "🔍": "search",
    "🔎": "search",
    "⏱": "timer",
    "⏰": "clock",
    "⚛": "atom",
    "🔌": "plug",
    "✂": "scissors",
    "🎯": "target",
    "📝": "square-pen",
    "💾": "save",
    "🌍": "globe",
    "🌎": "globe",
    "🌐": "globe",
    "🦖": "bird",
    "💚": "heart",
    "❤": "heart",
    "💙": "heart",
    "💪": "biceps-flexed",
    "💡": "lightbulb",
    "👍": "thumbs-up",
    "✅": "circle-check",
    "✔": "check",
    "✓": "check",
    "⚠": "triangle-alert",
    "🚧": "construction",
    "🚀": "rocket",
    "🔥": "flame",
    "⭐": "star",
    "🌟": "star",
    "🥇": "medal",
    "🏆": "trophy",
    "👥": "users",
    "👤": "user",
    "🟢": "circle-dot",
    "🟡": "circle-dot",
    "🔴": "circle-dot",
    "🍎": "apple",
    "🍌": "banana",
    "🍊": "citrus",
    "😉": "smile",
    "😄": "smile",
    "😀": "smile",
    "😊": "smile",
    "🙂": "smile",
    "😲": "circle-alert",
    "❌": "circle-x",
    "❗": "circle-alert",
    "ℹ": "info",
    "📦": "package",
    "🔒": "lock",
    "🔑": "key",
    "🔗": "link",
    "🛠": "wrench",
    "🔧": "wrench",
    "🎨": "palette",
    "🧩": "puzzle",
    "📚": "book-open",
    "📖": "book-open",
    "🐛": "bug",
    "🎉": "party-popper",
    "☁": "cloud",
    "🔔": "bell",
    "🚩": "flag",
    "📁": "folder",
}

_EMOJI_RE = None


def _emoji_re():
    import re

    global _EMOJI_RE
    if _EMOJI_RE is None:
        _EMOJI_RE = re.compile(r"[\U0001F000-\U0001FAFF☀-➓⭐⭕⏩-⏿ℹ]" r"[️‍\U0001F3FB-\U0001F3FF]*")
    return _EMOJI_RE


def emoji_icon(emoji: str) -> Optional[str]:
    """Lucide icon name for one emoji, or None when there is no stand-in."""
    base = emoji.replace("️", "").replace("‍", "")[:1]
    name = _EMOJI_ICONS.get(base)
    return name if name and is_lucide(name) else None


def convert_emoji_line(line: str, dropped: Optional[set] = None) -> str:
    """Swap emoji in one line of prose for inline <Icon /> tags.

    Headings and tag attributes lose their emoji instead: an icon tag in a heading breaks the
    anchor and the table of contents, and one inside an attribute would be read as text.
    Emoji with no Lucide stand-in are dropped and added to ``dropped``.
    """
    import re

    rx = _emoji_re()
    if not rx.search(line):
        return line

    def strip(seg: str) -> str:
        seg = re.sub(r'(?<=["\'>])[ \t]+(?=' + rx.pattern + ")", "", seg)
        return re.sub(rx.pattern + r"[ \t]*", "", seg)

    if re.match(r"^\s{0,3}#{1,6}\s", line):
        return re.sub(r"[ \t]{2,}", " ", strip(line)).rstrip()

    def swap(m):
        name = emoji_icon(m.group(0))
        if name:
            return f'<Icon icon="{name}" />'
        if dropped is not None:
            dropped.add(m.group(0))
        return ""

    out = []
    for part in re.split(r"(<[^<>\n]*>)", line):
        if part.startswith("<Icon"):
            out.append(part)
        elif part.startswith("<"):
            out.append(strip(part))
        else:
            out.append(rx.sub(swap, part))
    return re.sub(r"(?<=\S)[ \t]{2,}", " ", "".join(out)).replace("\x00", "")


def strip_emoji(text: str) -> str:
    """Remove every emoji from ``text``, along with the space left behind."""
    import re

    rx = _emoji_re()
    if not rx.search(text):
        return text
    text = re.sub(r"(?<=[\"'>(\[])[ \t]+(?=" + rx.pattern + ")", "", text)
    text = re.sub(rx.pattern + r"[ \t]*", "", text)
    text = re.sub(r"`\s*`", "", text)  # inline code that held only an emoji
    text = re.sub(r"(?<=\S)[ \t]+(?=[\"']$)", "", text)
    return text


def strip_emoji_everywhere(text: str) -> str:
    """Last pass over a finished page: no emoji survives, not even inside code fences.

    <Icon icon="..."/> tags are left alone so an emoji passed to ``icon`` is not mangled.
    """
    import re

    if not _emoji_re().search(text):
        return text
    out = []
    for line in text.split("\n"):
        if "<Icon" in line:
            line = "".join(
                p if p.startswith("<Icon") else strip_emoji(p)
                for p in re.split(r"(<Icon\b[^<>]*>)", line)
            )
        else:
            line = strip_emoji(line)
        out.append(line)
    return "\n".join(out)


def strip_emoji_json(value, key: str = ""):
    """Strip emoji from the display strings of a docs.json structure (never page paths)."""
    if isinstance(value, dict):
        return {k: strip_emoji_json(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [strip_emoji_json(v, key) for v in value]
    if isinstance(value, str) and key not in ("pages", "icon", "href", "url", "src"):
        return strip_emoji(value).strip()
    return value
