#!/usr/bin/env python3
"""
Utility functions for Mintlify Convert.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from . import docusaurus, ia
from .converter import (
    MAX_INPUT_BYTES,
    MintlifyConverter,
    SiteIndex,
    _fm_get,
    _normalize,
    _split_frontmatter,
    sanitize_page_key,
)


def check_paths(input_path: Path, output_path: Optional[Path]) -> Optional[str]:
    """Return an error message if the output would overwrite or nest with the input."""
    if output_path is None:
        return None
    try:
        src = Path(input_path).resolve()
        dst = Path(output_path).resolve()
    except (OSError, RuntimeError) as e:
        return f"Cannot resolve paths: {e}"
    if src == dst:
        return f"Output path must differ from the input path: {output_path}"
    if Path(input_path).is_dir():
        if dst.is_relative_to(src):
            return f"Output directory must not be inside the input directory: {output_path}"
        if src.is_relative_to(dst):
            return f"Input directory must not be inside the output directory: {input_path}"
    return None


def process_file(
    input_path: Path,
    output_path: Optional[Path] = None,
    converter: Optional[MintlifyConverter] = None,
    **kwargs,
) -> Tuple[bool, Optional[str]]:
    """Process a single MDX file.

    Args:
        input_path: Path to input MDX file
        output_path: Path to output file (optional)
        converter: MintlifyConverter instance (optional)
        **kwargs: Additional conversion options

    Returns:
        Tuple of (success, title)
    """
    try:
        input_path = Path(input_path)
        if input_path.is_symlink():
            print(f"Skipping symlink: {input_path}", file=sys.stderr)
            return False, None
        problem = check_paths(input_path, output_path)
        if problem is None and output_path is not None and Path(output_path).is_symlink():
            problem = f"Refusing to write through symlink: {output_path}"
        if problem:
            print(f"Error: {problem}", file=sys.stderr)
            return False, None
        if input_path.stat().st_size > MAX_INPUT_BYTES:
            print(
                f"Error: {input_path} is too large "
                f"(limit is {MAX_INPUT_BYTES // (1024 * 1024)} MiB)",
                file=sys.stderr,
            )
            return False, None

        with open(input_path, "r", encoding="utf-8") as f:
            content = f.read()

        if converter is None:
            converter = MintlifyConverter(
                Path(output_path).parent if output_path else None,
                download_assets=bool(kwargs.get("download_assets")),
                input_root=input_path.parent,
            )

        converted = converter.convert(content, source_file=input_path, **kwargs)

        for warning in converter.warnings:
            print(f"\u26a0 {input_path}: {warning}", file=sys.stderr)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(converted)
            print(f"\u2713 Converted: {input_path} -> {output_path}")

            if kwargs.get("validate") and converter.validation_errors:
                print(f"\u26a0 Validation warnings for {input_path}:")
                for error in converter.validation_errors:
                    print(f"  - {error}")
        else:
            print(converted)

        written = _fm_get(_split_frontmatter(converted)[0] or [], "title")
        return True, written or converter.extract_title(content)
    except Exception as e:
        print(f"\u2717 Error processing {input_path}: {str(e)}", file=sys.stderr)
        if kwargs.get("verbose"):
            import traceback

            traceback.print_exc()
        return False, None


class SiteMetadata(dict):
    """Page metadata for navigation, plus what else the scan learned about the site."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redirects: List[Dict] = []
        self.categories: Dict[str, Dict] = {}
        self.snippets: int = 0
        self.converted: int = 0  # pages and snippets written


def is_partial(relative_path: Path) -> bool:
    """Docusaurus ignores files and folders whose name starts with an underscore."""
    parts = relative_path.parts
    # A top-level snippets/ folder is what a previous conversion wrote.
    return any(part.startswith("_") for part in parts) or (
        len(parts) > 1 and parts[0] == "snippets"
    )


def snippet_path(relative_path: Path) -> str:
    """Where a partial lives in the output: _dir/_part.mdx -> snippets/dir/part.mdx."""
    parts = [part.lstrip("_") or part for part in relative_path.with_suffix("").parts]
    if parts[0] == "snippets":
        parts = parts[1:]
    return "snippets/" + "/".join(sanitize_page_key(p) for p in parts) + ".mdx"


def detect_static_dir(input_dir: Path, explicit=None) -> Optional[Path]:
    """The Docusaurus static folder: --static-dir, else ../static or ./static if present."""
    if explicit:
        return Path(explicit)
    for candidate in (input_dir.parent / "static", input_dir / "static"):
        if candidate.is_dir() and not candidate.is_symlink():
            return candidate
    return None


def _read_category(path: Path) -> Dict:
    """label/position/description from a Docusaurus _category_.yml or _category_.json."""
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}
    info: Dict = {}
    for line in text.splitlines():
        m = re.match(r"^(label|position|description)\s*:\s*(.*?)\s*(?:#.*)?$", line)
        if m:
            value = m.group(2).strip("\"'")
            if m.group(1) == "position":
                try:
                    info["position"] = float(value)
                except ValueError:
                    pass  # not a number: the folder keeps its alphabetical place
            else:
                info[m.group(1)] = value
    return info


def build_site_index(
    input_dir: Path, mdx_files: List[Path], route_prefix=None
) -> Tuple[SiteIndex, Dict]:
    """First pass over the docs: routes, renamed pages, heading anchors, partials and
    categories, so the second pass can rewrite links between pages."""
    index = SiteIndex()
    if route_prefix is None:
        route_prefix = "/docs" if input_dir.name == "docs" else ""
    if route_prefix:
        index.prefixes.append("/" + route_prefix.strip("/"))
    categories: Dict[str, Dict] = {}
    helper = MintlifyConverter()

    # Pages that keep their name claim it first; a renamed page that would land on a taken
    # name gets a numeric suffix instead of silently overwriting the other page.
    keys = [
        p.relative_to(input_dir).with_suffix("").as_posix()
        for p in mdx_files
        if not is_partial(p.relative_to(input_dir))
    ]
    # Names are compared case-insensitively: on macOS and Windows Case.md and case.md are one file.
    taken = set()
    for key in keys:
        if sanitize_page_key(key) == key and key.lower() not in taken:
            taken.add(key.lower())
    claimed = set()
    for key in keys:
        out_key = sanitize_page_key(key)
        if out_key == key and key.lower() in taken and key not in claimed:
            claimed.add(key)
            continue
        unique, n = out_key, 2
        while unique.lower() in taken:
            unique, n = f"{out_key}-{n}", n + 1
        taken.add(unique.lower())
        index.rename[key] = unique

    partial_anchors: Dict[Path, Dict[str, str]] = {}
    hosts: List[Tuple[str, Path, str]] = []
    for path in mdx_files:
        rel = path.relative_to(input_dir)
        if is_partial(rel):
            index.snippets[path.resolve()] = "/" + snippet_path(rel)
            try:
                _, pbody = _split_frontmatter(_normalize(path.read_text(encoding="utf-8")))
                partial_anchors[path.resolve()] = docusaurus.heading_anchors(pbody)
            except (OSError, UnicodeDecodeError):
                pass
            continue
        try:
            text = _normalize(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        key = rel.with_suffix("").as_posix()
        out_key = index.rename.get(key, key)
        fm, body = _split_frontmatter(text)
        fm = fm or []
        parent = key.rsplit("/", 1)[0] if "/" in key else ""
        leaf = key.rsplit("/", 1)[-1]

        routes = ["/" + key]
        if leaf.lower() in ("index", "readme"):
            routes.append("/" + parent if parent else "/")
        slug = _fm_get(fm, "slug")
        if slug:
            routes.append(
                slug.rstrip("/") or "/"
                if slug.startswith("/")
                else f"/{parent}/{slug}".replace("//", "/")
            )
        doc_id = _fm_get(fm, "id")
        if doc_id:
            routes.append(f"/{parent}/{doc_id}".replace("//", "/"))
        for route in routes:
            owner = index.routes.setdefault(route, out_key)
            if owner != out_key:
                print(
                    f"Warning: {rel.as_posix()} and {owner} both claim the route {route}; "
                    f"links to it go to {owner}",
                    file=sys.stderr,
                )

        anchors = docusaurus.heading_anchors(body)
        if anchors:
            index.anchors[out_key] = anchors
        hosts.append((out_key, path, body))
        position = _sidebar_position(path)
        index.pages[out_key] = {
            "title": helper.extract_title(text),
            "description": helper.extract_description(text),
            "position": position,
            "signals": ia.analyze(body),
            "source": rel.as_posix(),
        }

    # A page that imports a partial also owns the partial's headings.
    for out_key, path, body in hosts:
        for mod in re.findall(r"""^import\s+[^'"\n]+from\s+['"](\.[^'"\n]+)['"]""", body, re.M):
            target = Path(os.path.normpath(path.resolve().parent / mod))
            if target in partial_anchors and partial_anchors[target]:
                index.anchors.setdefault(out_key, {}).update(partial_anchors[target])

    for root, dirs, files in os.walk(input_dir, followlinks=False):
        dirs.sort()
        for name in files:
            if name in ("_category_.yml", "_category_.yaml", "_category_.json"):
                info = _read_category(Path(root) / name)
                if info:
                    folder = Path(root).relative_to(input_dir).as_posix()
                    categories[sanitize_page_key(folder) if folder != "." else ""] = info
    return index, categories


def process_directory(input_dir: Path, output_dir: Path, **kwargs) -> Dict:
    """Process all MDX files in a directory.

    Args:
        input_dir: Input directory containing MDX files
        output_dir: Output directory for converted files
        **kwargs: Additional conversion options (static_dir, route_prefix, ...)

    Returns:
        SiteMetadata (a dict of file metadata for navigation generation)

    Raises:
        ValueError: if the output directory equals or nests with the input directory
    """
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    problem = check_paths(input_dir, output_dir)
    if problem:
        raise ValueError(problem)

    skipped: list = []
    mdx_files = find_mdx_files(input_dir, skipped)
    for path in skipped:
        print(f"Warning: skipping symlink: {path}", file=sys.stderr)

    if not mdx_files:
        print(f"No MDX/MD files found in {input_dir}")
        return SiteMetadata()

    print(f"Found {len(mdx_files)} files to convert...")

    index, categories = build_site_index(input_dir, mdx_files, kwargs.get("route_prefix"))
    converter = MintlifyConverter(
        output_dir,
        download_assets=bool(kwargs.get("download_assets")),
        input_root=input_dir,
        static_dir=detect_static_dir(input_dir, kwargs.get("static_dir")),
        index=index,
        site_url=kwargs.get("site_url"),
    )
    success_count = 0
    file_metadata = SiteMetadata()
    file_metadata.categories = categories

    for mdx_file in mdx_files:
        relative_path = mdx_file.relative_to(input_dir)
        partial = is_partial(relative_path)
        key = relative_path.with_suffix("").as_posix()
        out_key = index.rename.get(key, key)
        if partial:
            output_path = output_dir / snippet_path(relative_path)
        else:
            output_path = output_dir / (out_key + relative_path.suffix)

        success, title = process_file(
            mdx_file,
            output_path,
            converter,
            **{
                **kwargs,
                "partial": partial,
                "page_key": None if partial else out_key,
                "source_rel": relative_path.as_posix(),
            },
        )
        if not success:
            continue
        success_count += 1
        file_metadata.converted += 1
        if partial:
            file_metadata.snippets += 1
            continue
        if out_key in file_metadata:
            print(
                f"Warning: {relative_path} collides with another page at '{out_key}'",
                file=sys.stderr,
            )
        info = index.pages.get(out_key, {})
        file_metadata[out_key] = {
            "title": title,
            "path": out_key,
            "position": _sidebar_position(mdx_file),
            "description": info.get("description", ""),
            "signals": info.get("signals", {}),
            "group": (
                relative_path.parent.as_posix()
                if relative_path.parent != Path(".")
                else "Documentation"
            ),
        }
        if out_key != key:
            file_metadata.redirects.append({"source": "/" + key, "destination": "/" + out_key})
            print(f"  renamed page: {key} -> {out_key} (redirect added)")

    print(f"\n\u2713 Successfully converted {success_count}/{len(mdx_files)} files")
    if file_metadata.snippets:
        print(f"\u2713 Wrote {file_metadata.snippets} partial(s) to /snippets")

    if converter.assets_copied:
        print(f"\u2713 Copied {len(converter.assets_copied)} assets to /images")

    return file_metadata


def _sidebar_position(path: Path) -> Optional[float]:
    """Docusaurus sidebar_position from the source frontmatter, if it is a number."""
    try:
        fm, _ = _split_frontmatter(_normalize(path.read_text(encoding="utf-8")))
        raw = _fm_get(fm, "sidebar_position") if fm is not None else None
        return float(raw) if raw is not None else None
    except (OSError, ValueError):
        return None


def find_mdx_files(directory: Path, skipped: Optional[list] = None) -> list[Path]:
    """Find all MDX and MD files in a directory, sorted, without following symlinks.

    Args:
        directory: Directory to search
        skipped: Optional list that receives the symlinked files and directories passed over

    Returns:
        List of MDX/MD file paths
    """
    found = []
    for root, dirs, files in os.walk(directory, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "node_modules")
        if skipped is not None:
            skipped.extend(Path(root) / d for d in dirs if (Path(root) / d).is_symlink())
        for name in sorted(files):
            path = Path(root) / name
            if path.suffix.lower() not in (".md", ".mdx"):
                continue
            if path.is_symlink():
                if skipped is not None:
                    skipped.append(path)
                continue
            found.append(path)
    return found


def ensure_output_directory(output_path: Path) -> None:
    """Ensure output directory exists.

    Args:
        output_path: Path to output directory
    """
    output_path.mkdir(parents=True, exist_ok=True)


def get_relative_path(file_path: Path, base_path: Path) -> str:
    """Get relative path string from file path to base path.

    Args:
        file_path: File path
        base_path: Base directory path

    Returns:
        Relative path string
    """
    try:
        return str(file_path.relative_to(base_path))
    except ValueError:
        # If file_path is not relative to base_path, return the filename
        return file_path.name


def validate_input_path(input_path: Path) -> bool:
    """Validate that input path exists and is readable.

    Args:
        input_path: Path to validate

    Returns:
        True if valid, False otherwise
    """
    if not input_path.exists():
        print(f"Error: {input_path} does not exist", file=sys.stderr)
        return False

    if input_path.is_file() and not input_path.suffix.lower() in [".md", ".mdx"]:
        print(f"Error: {input_path} is not an MDX or MD file", file=sys.stderr)
        return False

    return True


def print_conversion_summary(
    converted_count: int, total_count: int, assets_copied: int = 0, errors: Optional[list] = None
) -> None:
    """Print a summary of the conversion process.

    Args:
        converted_count: Number of files successfully converted
        total_count: Total number of files processed
        assets_copied: Number of assets copied
        errors: List of error messages
    """
    print(f"\n{'='*50}")
    print("CONVERSION SUMMARY")
    print(f"{'='*50}")
    print(f"Files converted: {converted_count}/{total_count}")

    if assets_copied > 0:
        print(f"Assets copied: {assets_copied}")

    if errors:
        print(f"Errors: {len(errors)}")
        for error in errors:
            print(f"  - {error}")

    if converted_count == total_count:
        print("✓ All files converted successfully!")
    else:
        print(f"⚠ {total_count - converted_count} files failed to convert")

    print(f"{'='*50}")
