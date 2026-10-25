#!/usr/bin/env python3
"""
Navigation, docs.json and mint.json generation for Mintlify Convert.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DOCS_JSON_SCHEMA_URL = "https://mintlify.com/docs.json"
DEFAULT_PRIMARY_COLOR = "#0D9373"
FIRST_GROUP = "Getting Started"

_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")
_SOCIAL_SCHEMES = ("http://", "https://")
_PAGE_SUFFIXES = (".mdx", ".md")


def _clean_path(raw) -> Optional[str]:
    """Normalise a page path to a forward-slash, extension-less relative path."""
    if not isinstance(raw, str):
        return None
    path = raw.strip().replace("\\", "/")
    for suffix in _PAGE_SUFFIXES:
        if path.lower().endswith(suffix):
            path = path[: -len(suffix)]
            break
    parts = [part for part in path.split("/") if part not in ("", ".")]
    if not parts or ".." in parts:
        return None
    return "/".join(parts)


def _group_title(name) -> str:
    if not isinstance(name, str) or not name.strip():
        return "Documentation"
    return name.replace("-", " ").replace("_", " ").strip().title()


def _page_title(meta: Dict, path: str) -> str:
    title = meta.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return path.rsplit("/", 1)[-1].replace("-", " ").replace("_", " ").title()


def _group_sort_key(title: str):
    # "Getting Started" first, "Documentation" next (legacy behaviour), then A-Z.
    return (title != FIRST_GROUP, title != "Documentation", title.casefold(), title)


def _build_groups(file_metadata: Optional[Dict], sort_pages: bool = False) -> List[Dict]:
    """Return [{'group': title, 'pages': [path, ...]}] in navigation order."""
    groups: Dict[str, List[Tuple[str, str]]] = {}
    seen = set()

    for key, meta in sorted((file_metadata or {}).items(), key=lambda kv: str(kv[0])):
        if not isinstance(meta, dict):
            continue
        path = _clean_path(meta.get("path", key))
        if path is None or path in seen:
            continue
        seen.add(path)
        title = _group_title(meta.get("group"))
        groups.setdefault(title, []).append((_page_title(meta, path), path))

    result = []
    for title in sorted(groups, key=_group_sort_key):
        pages = groups[title]
        if sort_pages:
            pages = sorted(pages, key=lambda tp: (tp[0].casefold(), tp[1]))
        result.append({"group": title, "pages": [path for _, path in pages]})
    return result


def _valid_url(value, schemes=_SOCIAL_SCHEMES) -> Optional[str]:
    if isinstance(value, str) and value.strip().lower().startswith(schemes):
        return value.strip()
    return None


def _check_color(value, label: str) -> Optional[str]:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not _HEX_COLOR.match(value):
        raise ValueError(f"{label} must be a hex color like #0D9373, got {value!r}")
    return value


def _write_json(config: Dict, output_path) -> None:
    path = Path(output_path)
    if path.is_symlink():
        raise ValueError(f"Refusing to write through symlink: {path}")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def generate_docs_json(
    file_metadata: Optional[Dict],
    output_file,
    project_name: str = "Documentation",
    primary_color: Optional[str] = None,
    light_color: Optional[str] = None,
    dark_color: Optional[str] = None,
    support_url: Optional[str] = None,
    dashboard_url: Optional[str] = None,
    twitter: Optional[str] = None,
    github: Optional[str] = None,
    linkedin: Optional[str] = None,
    sort_pages: bool = False,
    **_ignored,
):
    """Write a minimal docs.json (theme "mint") valid against the Mintlify schema.

    Keys whose values are unset are omitted; nothing is filled with placeholders.
    Raises ValueError for malformed colors.
    """
    colors = {"primary": _check_color(primary_color, "primary_color") or DEFAULT_PRIMARY_COLOR}
    for key, value in (("light", light_color), ("dark", dark_color)):
        checked = _check_color(value, f"{key}_color")
        if checked:
            colors[key] = checked

    groups = _build_groups(file_metadata, sort_pages)
    config: Dict = {
        "$schema": DOCS_JSON_SCHEMA_URL,
        "theme": "mint",
        "name": (project_name or "").strip() or "Documentation",
        "colors": colors,
        # The schema rejects an empty "groups" array but accepts an empty "pages" one.
        "navigation": {"groups": groups} if groups else {"pages": []},
    }

    links = []
    support = _valid_url(support_url, _SOCIAL_SCHEMES + ("mailto:",))
    if support:
        links.append({"label": "Support", "href": support})
    navbar: Dict = {}
    if links:
        navbar["links"] = links
    dashboard = _valid_url(dashboard_url)
    if dashboard:
        navbar["primary"] = {"type": "button", "label": "Dashboard", "href": dashboard}
    if navbar:
        config["navbar"] = navbar

    socials = {}
    for name, value in (("x", twitter), ("github", github), ("linkedin", linkedin)):
        url = _valid_url(value)
        if url:
            socials[name] = url
    if socials:
        config["footer"] = {"socials": socials}

    _write_json(config, output_file)
    print(f"\u2713 Generated docs.json at {output_file}")


def generate_enhanced_mint_json(file_metadata: Dict, output_path: Path, **kwargs):
    """Generate a legacy mint.json with grouped navigation (no placeholder values)."""
    primary = _check_color(kwargs.get("primary_color"), "primary_color") or DEFAULT_PRIMARY_COLOR
    light = _check_color(kwargs.get("light_color"), "light_color")
    dark = _check_color(kwargs.get("dark_color"), "dark_color")

    colors: Dict = {"primary": primary}
    if light:
        colors["light"] = light
    if dark:
        colors["dark"] = dark
    if light:
        colors["anchors"] = {"from": primary, "to": light}

    mint_config: Dict = {
        "name": (kwargs.get("project_name") or "").strip() or "Documentation",
        "colors": colors,
        "navigation": _build_groups(file_metadata, bool(kwargs.get("sort_pages"))),
    }

    support = _valid_url(kwargs.get("support_url"), _SOCIAL_SCHEMES + ("mailto:",))
    if support:
        mint_config["topbarLinks"] = [{"name": "Support", "url": support}]
    dashboard = _valid_url(kwargs.get("dashboard_url"))
    if dashboard:
        mint_config["topbarCtaButton"] = {"name": "Dashboard", "url": dashboard}

    socials = {}
    for name in ("twitter", "github", "linkedin"):
        url = _valid_url(kwargs.get(name))
        if url:
            socials[name] = url
    if socials:
        mint_config["footerSocials"] = socials

    _write_json(mint_config, output_path)
    print(f"\u2713 Generated enhanced mint.json at {output_path}")


def create_basic_mint_json(output_path: Path, project_name: str = "Documentation"):
    """Create a basic mint.json file for simple setups."""
    basic_config = {
        "name": project_name,
        "logo": {"dark": "/logo/dark.svg", "light": "/logo/light.svg"},
        "favicon": "/favicon.svg",
        "colors": {"primary": "#0D9373", "light": "#07C983", "dark": "#0D9373"},
        "navigation": [{"group": "Getting Started", "pages": ["getting-started"]}],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(basic_config, f, indent=2)

    print(f"✓ Generated basic mint.json at {output_path}")


def validate_mint_json(mint_json_path: Path) -> bool:
    """Validate mint.json structure."""
    try:
        with open(mint_json_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        required_fields = ["name", "navigation"]
        for field in required_fields:
            if field not in config:
                print(f"Error: Missing required field '{field}' in mint.json")
                return False

        # Validate navigation structure
        if not isinstance(config["navigation"], list):
            print("Error: 'navigation' must be a list")
            return False

        for item in config["navigation"]:
            if not isinstance(item, dict) or "group" not in item or "pages" not in item:
                print("Error: Each navigation item must have 'group' and 'pages' fields")
                return False

        print("✓ mint.json validation passed")
        return True

    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in mint.json: {e}")
        return False
    except Exception as e:
        print(f"Error validating mint.json: {e}")
        return False
