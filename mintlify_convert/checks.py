#!/usr/bin/env python3
"""
Checks on a converted site: internal links, anchors, images and docs.json pages.

A converted page can look fine on its own and still point at a page that was renamed, an anchor
that Mintlify spells differently, or an image that was never copied. These checks read the
output folder and report each dead reference.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from .converter import _mask_code, _normalize, _restore_code, _scan_links, _split_frontmatter
from .docusaurus import _slug

_PAGE_SUFFIXES = (".mdx", ".md")
_HREF_RE = re.compile(r"""\b(?:href|src)=(?:"([^"]*)"|'([^']*)')""")
_HEADING_RE = re.compile(r"^#{1,6}[ \t]+(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)


def _page_file(root: Path, route: str) -> Optional[Path]:
    rel = route.strip("/")
    for candidate in (rel, rel + "/index" if rel else "index"):
        for suffix in _PAGE_SUFFIXES:
            path = root / (candidate + suffix)
            if path.is_file():
                return path
    return None


def _find_root(path: Path) -> Path:
    """The output root of a page: the folder that holds docs.json (else the page's own folder)."""
    for parent in path.parents:
        if (parent / "docs.json").is_file() or (parent / "mint.json").is_file():
            return parent
    return path.parent


def _anchors(path: Path, cache: Dict[Path, Set[str]]) -> Set[str]:
    if path not in cache:
        text = _normalize(path.read_text(encoding="utf-8"))
        _, body = _split_frontmatter(text)
        masked, store = _mask_code(body)
        found: Set[str] = set()
        counts: Dict[str, int] = {}
        for m in _HEADING_RE.finditer(masked):
            heading = _restore_code(m.group(1), store)
            slug = _slug(re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading))
            n = counts.get(slug, 0)
            counts[slug] = n + 1
            found.add(slug if n == 0 else f"{slug}-{n}")
        found.update(re.findall(r"""<(?:div|span|a)\b[^>]*\bid=["']([^"']+)["']""", masked))
        # Headings of imported snippets belong to the page that imports them.
        for mod in re.findall(
            r"""^import\s+[^'"\n]+from\s+['"](/snippets/[^'"\n]+)['"]""", masked, re.M
        ):
            snippet = _find_root(path) / mod.lstrip("/")
            if snippet.is_file():
                found |= _anchors(snippet, cache)
        cache[path] = found
    return cache[path]


def _nav_pages(node) -> List[str]:
    pages: List[str] = []
    if isinstance(node, str):
        pages.append(node)
    elif isinstance(node, dict):
        for key in ("pages", "groups", "tabs", "anchors", "dropdowns", "versions", "languages"):
            pages.extend(_nav_pages(node.get(key)))
    elif isinstance(node, list):
        for item in node:
            pages.extend(_nav_pages(item))
    return pages


def check_site(output_dir) -> List[str]:
    """Return one message per dead internal link, anchor, image or navigation entry."""
    root = Path(output_dir)
    problems: List[str] = []
    cache: Dict[Path, Set[str]] = {}
    files = sorted(
        p
        for p in root.rglob("*")
        if p.suffix in _PAGE_SUFFIXES
        and p.is_file()
        and "snippets" not in p.relative_to(root).parts[:1]
    )

    for path in files:
        rel = path.relative_to(root).as_posix()
        _, text = _split_frontmatter(_normalize(path.read_text(encoding="utf-8")))
        masked, _ = _mask_code(text)
        targets = [t for _, _, _, t in _scan_links(masked, images=False)]
        targets += [t for _, _, _, t in _scan_links(masked, images=True)]
        for m in _HREF_RE.finditer(masked):
            targets.append(m.group(1) if m.group(1) is not None else m.group(2))

        for raw in targets:
            target = raw.strip().split()[0] if raw.strip() else ""
            if not target or re.match(r"^(?:[A-Za-z][\w+.-]*:|//)", target):
                continue
            base, _, frag = target.partition("#")
            base = base.split("?")[0]
            if not base:  # same-page anchor
                dest = path
            elif base.startswith("/"):
                dest = _page_file(root, base)
                if dest is None and not (root / base.lstrip("/")).is_file():
                    problems.append(f"{rel}: dead link {target}")
                    continue
                if dest is None:
                    continue
            else:
                continue  # relative leftovers are reported by the converter
            if frag and dest.suffix in _PAGE_SUFFIXES:
                if frag not in _anchors(dest, cache):
                    problems.append(
                        f"{rel}: missing anchor #{frag} in {dest.relative_to(root).as_posix()}"
                    )

    config = root / "docs.json"
    if config.is_file():
        try:
            nav = json.loads(config.read_text(encoding="utf-8")).get("navigation")
        except ValueError:
            problems.append("docs.json: not valid JSON")
            nav = None
        for page in _nav_pages(nav):
            if _page_file(root, page) is None:
                problems.append(f"docs.json: page '{page}' has no file")
    return problems
