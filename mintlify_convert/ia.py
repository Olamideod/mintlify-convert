#!/usr/bin/env python3
"""
Information architecture for the generated docs.json.

Pages are sorted into the four Diataxis modes, plus a "Get started" entry point:

    start      introduction, installation, quickstart
    tutorial   learning-oriented lessons
    howto      goal-oriented guides
    concept    understanding-oriented explanation
    reference  information-oriented lookup material (API, CLI, configuration)

Documentation lives in one tab and reference material in a separate "API reference" tab, no
matter how the source site grouped its folders. The classifier looks at folder names, file
names, titles and the shape of the content. When it guesses wrong, an IA config file moves a
page (see ``load_ia_config``).
"""

import fnmatch
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

START, TUTORIAL, HOWTO, CONCEPT, REFERENCE = "start", "tutorial", "howto", "concept", "reference"
KINDS = (START, TUTORIAL, HOWTO, CONCEPT, REFERENCE)

# Group titles and Lucide icons for each mode, in sidebar order.
SECTIONS = {
    START: ("Get started", "rocket"),
    TUTORIAL: ("Tutorials", "graduation-cap"),
    HOWTO: ("How-to guides", "list-checks"),
    CONCEPT: ("Concepts", "lightbulb"),
}
DOCS_TAB = ("Documentation", "book-open")
REFERENCE_TAB = ("API reference", "square-terminal")
CORE_REFERENCE_GROUP = "Core reference"

_START_STEMS = {
    "introduction", "intro", "overview", "installation", "install", "quickstart",
    "quick-start", "getting-started", "setup", "playground", "welcome", "index", "readme",
}  # fmt: skip
_NEXT_STEPS_STEMS = {"whats-next", "what-s-next", "next-steps", "next", "where-to-go-next"}
_REFERENCE_DIRS = {"api", "apis", "reference", "references", "cli", "schema", "schemas", "sdk"}
_TUTORIAL_DIRS = {"tutorial", "tutorials", "learn", "lessons", "codelabs"}
_HOWTO_DIRS = {
    "guides", "guide", "how-to", "howto", "recipes", "cookbook", "deployment", "deploy",
    "migration", "migrate", "upgrade", "upgrading", "troubleshooting", "integrations",
    "i18n", "examples",
}  # fmt: skip
_CONCEPT_DIRS = {
    "concepts", "concept", "explanation", "explanations", "advanced", "architecture",
    "background", "about", "internals", "design", "faq",
}  # fmt: skip
# Folder names that only say which mode a page is in; they add nothing as a group title.
_GENERIC_DIRS = (
    _REFERENCE_DIRS | _TUTORIAL_DIRS | {"guides", "guide", "how-to", "howto", "concepts",
                                         "concept", "explanation", "explanations"}
)  # fmt: skip

_TITLE_REFERENCE = re.compile(
    r"\b(api|apis|cli|reference|options|commands?|schema|config(?:uration)? file|sdk)\b", re.I
)
_TITLE_HOWTO = re.compile(
    r"^(how to|creat|add|us(?:e|ing)|deploy|configur|migrat|upgrad|set(?:ting)? up|install|"
    r"writ|manag|customi[sz]|enabl|build|integrat|publish|translat|troubleshoot)",
    re.I,
)
_TITLE_CONCEPT = re.compile(
    r"\b(overview|architecture|concepts?|understanding|how it works|why|principles|philosophy|"
    r"design|routing|rendering|internals|static site generation|ssg|client)\b",
    re.I,
)
_TITLE_TUTORIAL = re.compile(r"\b(tutorial|walkthrough|your first|learn|build a)\b", re.I)

_ACRONYMS = {
    "api": "API", "apis": "APIs", "cli": "CLI", "seo": "SEO", "ssg": "SSG", "sdk": "SDK",
    "url": "URL", "urls": "URLs", "html": "HTML", "css": "CSS", "json": "JSON", "yaml": "YAML",
    "ui": "UI", "ux": "UX", "ci": "CI", "cd": "CD", "pwa": "PWA", "mdx": "MDX", "faq": "FAQ",
    "graphql": "GraphQL", "oauth": "OAuth", "sso": "SSO", "ssr": "SSR", "dns": "DNS",
    "i18n": "Internationalization", "l10n": "Localization", "a11y": "Accessibility",
    "github": "GitHub", "gitlab": "GitLab", "eslint": "ESLint", "typescript": "TypeScript",
    "javascript": "JavaScript", "nodejs": "Node.js", "npm": "npm", "pnpm": "pnpm",
    "vercel": "Vercel", "netlify": "Netlify", "docusaurus": "Docusaurus", "misc": "Miscellaneous",
    "devops": "DevOps", "ios": "iOS", "macos": "macOS",
}  # fmt: skip
_SMALL_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "vs",
}


def humanize(name: str, title_case: bool = False) -> str:
    """'plugin-methods' -> 'Plugin methods' (or 'Plugin Methods' with title_case).

    Known acronyms and brand names keep their case: 'api' -> 'API', 'eslint' -> 'ESLint'.
    """
    words = [w for w in re.split(r"[-_\s]+", str(name).strip()) if w]
    out = []
    for i, word in enumerate(words):
        low = word.lower()
        if low in _ACRONYMS:
            out.append(_ACRONYMS[low])
        elif i == 0 or title_case:
            out.append(word[:1].upper() + word[1:].lower() if word.islower() else word)
        else:
            out.append(word.lower() if word.islower() else word)
    return " ".join(out) or str(name)


# --- content signals ---------------------------------------------------------


def analyze(text: str) -> Dict[str, int]:
    """Cheap structural counts used to tell a guide from a reference page."""
    code_blocks = len(re.findall(r"^[ \t]*(?:```|~~~)", text, re.MULTILINE)) // 2
    return {
        "words": len(re.findall(r"\w+", text)),
        "steps": len(re.findall(r"^[ \t]*\d{1,3}\.[ \t]+\S", text, re.MULTILINE)),
        "tables": len(re.findall(r"^\|[ \t]*:?-{3,}", text, re.MULTILINE)),
        "code_blocks": code_blocks,
        "code_headings": len(re.findall(r"^#{2,4}[ \t]+`[^`\n]+`", text, re.MULTILINE)),
        "type_lines": len(
            re.findall(r"^[ \t]*[-*][ \t]+(?:Type|Default|Required|Optional)\b", text, re.MULTILINE)
        ),
    }


def classify(key: str, meta: Dict) -> Tuple[str, str]:
    """Return (kind, reason) for a page. ``key`` is the page path without extension."""
    parts = [p.lower() for p in key.split("/")]
    stem = parts[-1]
    folders = parts[:-1]
    title = str(meta.get("title") or "")
    sig = meta.get("signals") or {}

    scores = {k: 0.0 for k in KINDS}
    why: Dict[str, List[str]] = {k: [] for k in KINDS}

    def add(kind: str, points: float, reason: str) -> None:
        scores[kind] += points
        why[kind].append(reason)

    if stem in _NEXT_STEPS_STEMS:
        add(START, 10, f"'{stem}' points to what to read next")
    if not folders and stem in _START_STEMS:
        add(START, 10, f"'{stem}' is an entry-point page")
    for folder in folders:
        if folder in _REFERENCE_DIRS:
            add(REFERENCE, 6, f"folder '{folder}'")
        if folder in _TUTORIAL_DIRS:
            add(TUTORIAL, 6, f"folder '{folder}'")
        if folder in _HOWTO_DIRS:
            add(HOWTO, 4, f"folder '{folder}'")
        if folder in _CONCEPT_DIRS:
            add(CONCEPT, 4, f"folder '{folder}'")
    if stem in _REFERENCE_DIRS or re.search(r"(^|-)(api|cli)(-|$)", stem):
        add(REFERENCE, 4, f"file name '{stem}'")
    if _TITLE_REFERENCE.search(title):
        add(REFERENCE, 3, "title names an API, CLI or options")
    if _TITLE_TUTORIAL.search(title):
        add(TUTORIAL, 5, "title says tutorial")
    if _TITLE_HOWTO.match(title):
        add(HOWTO, 3, "title is a task")
    if _TITLE_CONCEPT.search(title):
        add(CONCEPT, 2.5, "title names a concept")
    if (
        folders
        and not any(f in _REFERENCE_DIRS for f in folders)
        and (
            re.search(r"(^|-)(intro|introduction|overview)$", stem)
            or re.fullmatch(r"introduction|intro|overview", title.lower())
        )
    ):
        add(CONCEPT, 8, "introduces a topic")
    if sig.get("code_headings", 0) >= 3:
        add(REFERENCE, min(sig["code_headings"] * 0.5, 4), "many code-named headings")
    if sig.get("type_lines", 0) >= 3:
        add(REFERENCE, 3, "lists Type/Default fields")
    if sig.get("tables", 0) >= 2:
        add(REFERENCE, 1.5, "several tables")
    if sig.get("steps", 0) >= 2:
        add(HOWTO, min(sig["steps"] * 0.5, 3), "numbered steps")

    best = max(KINDS, key=lambda k: (scores[k], -KINDS.index(k)))
    if scores[best] <= 0:
        # Nothing matched: procedural pages (code, steps) are guides, the rest is explanation.
        words = max(sig.get("words", 0), 1)
        if sig.get("steps", 0) >= 1 or sig.get("code_blocks", 0) * 150 >= words:
            return HOWTO, "defaulted: mostly code or steps"
        return CONCEPT, "defaulted: mostly prose"
    return best, "; ".join(why[best])


# --- IA config ---------------------------------------------------------------


def load_ia_config(path) -> Dict:
    """Read an IA config: {"pages": {glob: {...}}, "groups": {...}, "tabs": {...}}.

    ``pages`` maps a page path (a glob over the output path, no extension) to
    ``{"section": "start|tutorial|howto|concept|reference", "group": "Title", "position": n}``.
    ``groups`` renames a folder-derived group: {"Miscellaneous": "Tooling"}.
    ``tabs`` renames a tab: {"Documentation": "Docs", "API reference": "API"}.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("IA config must be a JSON object")
    for name in ("pages", "groups", "tabs"):
        if not isinstance(data.get(name) or {}, dict):
            raise ValueError(f"IA config: '{name}' must be an object")
    for name in ("groups", "tabs"):
        for old, new in (data.get(name) or {}).items():
            if not isinstance(new, str) or not new.strip():
                raise ValueError(f"IA config: '{name}' maps '{old}' to a non-empty name")
    tabs = data.get("tabs") or {}
    renamed = [tabs.get(t, t) for t in (DOCS_TAB[0], REFERENCE_TAB[0])]
    if len(set(renamed)) < 2:
        raise ValueError("IA config: the two tabs need different names")
    for pattern, rule in (data.get("pages") or {}).items():
        if not isinstance(rule, dict):
            raise ValueError(f"IA config: rule for '{pattern}' must be an object")
        if "group" in rule and not (isinstance(rule["group"], str) and rule["group"].strip()):
            raise ValueError(f"IA config: group for '{pattern}' must be a non-empty string")
        pos = rule.get("position")
        if pos is not None and (isinstance(pos, bool) or not isinstance(pos, (int, float))):
            raise ValueError(f"IA config: position for '{pattern}' must be a number")
        section = rule.get("section")
        if section is not None and section not in KINDS:
            raise ValueError(
                f"IA config: '{pattern}' has unknown section '{section}' "
                f"(use one of {', '.join(KINDS)})"
            )
    return data


def _override(key: str, config: Optional[Dict]) -> Dict:
    merged: Dict = {}
    for pattern, rule in ((config or {}).get("pages") or {}).items():
        if fnmatch.fnmatchcase(key, pattern):
            merged.update(rule)
    return merged


# --- navigation tree ---------------------------------------------------------


class _Node:
    def __init__(self) -> None:
        self.pages: List[Tuple[Tuple, str]] = []  # (sort key, page path)
        self.children: Dict[str, "_Node"] = {}
        self.order: float = float("inf")  # smallest child position, for ordering subgroups
        self.explicit = False  # named by an IA config rule: never flattened away


def _position(meta: Dict, rule: Optional[Dict] = None) -> float:
    pos = (rule or {}).get("position")
    if pos is None:
        pos = meta.get("position")
    return (
        float(pos) if isinstance(pos, (int, float)) and not isinstance(pos, bool) else float("inf")
    )


def _page_sort_key(key: str, meta: Dict, sort_pages: bool, rule: Optional[Dict] = None) -> Tuple:
    """Index-like pages first, then sidebar position (unless sorting A-Z), then title."""
    leaf = key.rsplit("/", 1)[-1]
    is_index = leaf.lower() in ("index", "readme", "introduction", "intro", "overview")
    title = str(meta.get("title") or key).casefold()
    is_next = leaf.lower() in _NEXT_STEPS_STEMS
    if is_next:
        return (True, True, 0.0, title, key)  # "what's next" closes its group
    if sort_pages and (rule or {}).get("position") is None:
        return (not is_index, is_next, 0.0, title, key)
    return (not is_index, is_next, _position(meta, rule), title, key)


def _topic_path(key: str, drop: int = 0) -> List[str]:
    """Folder names that become nested groups, minus folders that only name the mode."""
    folders = key.split("/")[:-1]
    kept = [f for f in folders if f.lower() not in _GENERIC_DIRS]
    return kept[drop:]


def _insert(
    root: _Node, path: List[str], entry: Tuple[Tuple, str], position: float, explicit: bool = False
) -> None:
    node = root
    for name in path[:2]:  # two levels of subgroups is as deep as a sidebar should go
        node = node.children.setdefault(name, _Node())
        node.explicit = node.explicit or explicit
        node.order = min(node.order, position)
    node.pages.append(entry)
    node.order = min(node.order, position)


def _to_items(
    node: _Node,
    renames: Dict[str, str],
    categories: Optional[Dict[str, Dict]] = None,
    prefix: Tuple[str, ...] = (),
) -> List:
    """Pages first, then subgroups; a subgroup holding one page is flattened into its parent."""
    items: List = [p for _, p in sorted(node.pages)]

    def rank(name: str):  # noqa: E306
        cat = _category_info(categories, prefix + (name,))
        pos = cat.get("position") if isinstance(cat.get("position"), (int, float)) else None
        return (pos if pos is not None else node.children[name].order, name.casefold())

    for name in sorted(node.children, key=rank):
        child = node.children[name]
        sub = _to_items(child, renames, categories, prefix + (name,))
        if len(sub) == 1 and isinstance(sub[0], str) and not child.explicit:
            items.append(sub[0])
            continue
        label = _category_label(categories, prefix + (name,)) or humanize(name)
        label = renames.get(label, label)
        items.append({"group": label, "pages": sub})
    return items


def _category_info(categories: Optional[Dict[str, Dict]], path: Tuple[str, ...]) -> Dict:
    """The Docusaurus _category_.yml of a folder, matched by the last segments of its path."""
    for folder, info in (categories or {}).items():
        if path and folder.split("/")[-len(path) :] == list(path):
            return info
    return {}


def _category_label(categories: Optional[Dict[str, Dict]], path: Tuple[str, ...]) -> Optional[str]:
    label = _category_info(categories, path).get("label")
    return str(label) if label else None


def build_diataxis_navigation(
    file_metadata: Dict,
    sort_pages: bool = False,
    config: Optional[Dict] = None,
    categories: Optional[Dict[str, Dict]] = None,
) -> Dict:
    """Return a docs.json ``navigation`` object: a Documentation tab plus an API reference tab.

    Each page gets a ``section`` (and the reason) stored back into its metadata so callers can
    report the decisions. When only one tab would be left, plain ``groups`` are returned.
    """
    config = config or {}
    group_renames = config.get("groups") or {}
    tab_renames = config.get("tabs") or {}
    seen = set()
    sections: Dict[str, List[Tuple[str, Dict, Dict]]] = {k: [] for k in KINDS}

    for raw_key, meta in sorted((file_metadata or {}).items(), key=lambda kv: str(kv[0])):
        if not isinstance(meta, dict):
            continue
        key = str(meta.get("path") or raw_key)
        if key in seen:
            continue
        seen.add(key)
        rule = _override(key, config)
        kind, reason = classify(key, meta)
        if rule.get("section") in KINDS:
            kind, reason = rule["section"], "set by IA config"
        meta["section"], meta["section_reason"] = kind, reason
        sections[kind].append((key, meta, rule))

    def fill(entries: List[Tuple[str, Dict, Dict]]) -> _Node:
        root = _Node()
        for key, meta, rule in entries:
            path = [str(rule["group"])] if rule.get("group") else _topic_path(key)
            sort_key = _page_sort_key(key, meta, sort_pages, rule)
            _insert(root, path, (sort_key, key), _position(meta, rule), bool(rule.get("group")))
        return root

    def docs_group(kind: str) -> Optional[Dict]:
        if not sections[kind]:
            return None
        title, icon = SECTIONS[kind]
        items = _to_items(fill(sections[kind]), group_renames, categories)
        # A section that is one folder deep (Concepts = everything under "advanced") would show
        # a group inside a group of the same subject; hoist it.
        if len(items) == 1 and isinstance(items[0], dict):
            items = items[0]["pages"]
        return {"group": group_renames.get(title, title), "icon": icon, "pages": items}

    doc_groups = [g for g in (docs_group(k) for k in (START, TUTORIAL, HOWTO, CONCEPT)) if g]

    ref_group = None
    if sections[REFERENCE]:
        root = fill(sections[REFERENCE])
        ref_group = []
        if root.pages:
            name = group_renames.get(CORE_REFERENCE_GROUP, CORE_REFERENCE_GROUP)
            ref_group.append({"group": name, "pages": [p for _, p in sorted(root.pages)]})
        root.pages = []
        loose = []
        for item in _to_items(root, group_renames, categories):
            (ref_group if isinstance(item, dict) else loose).append(item)
        if loose:  # one-page folders: they join the core group instead of one "More" group each
            name = group_renames.get(CORE_REFERENCE_GROUP, CORE_REFERENCE_GROUP)
            core = next((g for g in ref_group if g["group"] == name), None)
            if core is None:
                core = {"group": name, "pages": []}
                ref_group.insert(0, core)
            core["pages"].extend(loose)

    def tab(spec, groups):
        label = tab_renames.get(spec[0], spec[0])
        return {"tab": label, "icon": spec[1], "groups": groups}

    if doc_groups and ref_group:
        return {"tabs": [tab(DOCS_TAB, doc_groups), tab(REFERENCE_TAB, ref_group)]}
    if ref_group and not doc_groups:
        return {"tabs": [tab(REFERENCE_TAB, ref_group)]}
    return {"groups": doc_groups}


def describe_decisions(file_metadata: Dict) -> List[str]:
    """One line per page: where it went and why, for --verbose output."""
    lines = []
    for key, meta in sorted(file_metadata.items()):
        if isinstance(meta, dict) and meta.get("section"):
            lines.append(f"  {meta['section']:<9} {key}  ({meta.get('section_reason', '')})")
    return lines
