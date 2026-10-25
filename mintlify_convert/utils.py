#!/usr/bin/env python3
"""
Utility functions for Mintlify Convert.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Tuple, Optional

from .converter import MAX_INPUT_BYTES, MintlifyConverter


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
    input_path: Path, output_path: Path = None, converter: MintlifyConverter = None, **kwargs
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

        return True, converter.extract_title(content)
    except Exception as e:
        print(f"\u2717 Error processing {input_path}: {str(e)}", file=sys.stderr)
        if kwargs.get("verbose"):
            import traceback

            traceback.print_exc()
        return False, None


def process_directory(input_dir: Path, output_dir: Path, **kwargs) -> Dict:
    """Process all MDX files in a directory.

    Args:
        input_dir: Input directory containing MDX files
        output_dir: Output directory for converted files
        **kwargs: Additional conversion options

    Returns:
        Dictionary of file metadata for navigation generation

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
        return {}

    print(f"Found {len(mdx_files)} files to convert...")

    converter = MintlifyConverter(
        output_dir, download_assets=bool(kwargs.get("download_assets")), input_root=input_dir
    )
    success_count = 0
    file_metadata = {}

    for mdx_file in mdx_files:
        relative_path = mdx_file.relative_to(input_dir)
        output_path = output_dir / relative_path

        success, title = process_file(mdx_file, output_path, converter, **kwargs)
        if success:
            success_count += 1
            key = relative_path.with_suffix("").as_posix()
            if key in file_metadata:
                print(
                    f"Warning: {relative_path} collides with another page at '{key}'",
                    file=sys.stderr,
                )
            file_metadata[key] = {
                "title": title,
                "path": key,
                "group": (
                    relative_path.parent.as_posix()
                    if relative_path.parent != Path(".")
                    else "Documentation"
                ),
            }

    print(f"\n\u2713 Successfully converted {success_count}/{len(mdx_files)} files")

    if converter.assets_copied:
        print(f"\u2713 Copied {len(converter.assets_copied)} assets to /images")

    return file_metadata


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
        dirs.sort()
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
    converted_count: int, total_count: int, assets_copied: int = 0, errors: list = None
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
