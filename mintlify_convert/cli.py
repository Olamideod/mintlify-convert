#!/usr/bin/env python3
"""
Command-line interface for Mintlify Convert.
"""

import argparse
import sys
from pathlib import Path

from .utils import check_paths, find_mdx_files, process_file, process_directory
from .navigation import generate_docs_json, generate_enhanced_mint_json
from . import ia
from .checks import check_site


def main(argv=None):
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Convert MDX files to Mintlify format (v2 - Enhanced)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert a single file
  mintlify-convert input.mdx -o output.mdx

  # Convert a directory with assets
  mintlify-convert docs/ -o mintlify-docs/ --download-assets

  # Generate docs.json arranged by Diataxis, with API reference in its own tab
  mintlify-convert docs/ -o mintlify-docs/ --generate-config --sort-pages

  # Keep the source folders as navigation groups instead
  mintlify-convert docs/ -o mintlify-docs/ --generate-config --structure folders

  # Move pages the classifier got wrong (see --ia-config in the README)
  mintlify-convert docs/ -o mintlify-docs/ --generate-config --ia-config ia.json --explain-ia

  # Validate output
  mintlify-convert docs/ -o mintlify-docs/ --validate

  # Full conversion with all features
  mintlify-convert docs/ -o mintlify-docs/ \\
    --generate-config \\
    --download-assets \\
    --validate \\
    --sort-pages \\
    --project-name "My API Docs"
        """,
    )

    parser.add_argument("input", type=str, help="Input MDX file or directory")
    parser.add_argument("-o", "--output", type=str, help="Output file or directory")

    # Frontmatter options
    parser.add_argument("--icon", type=str, help="Icon for frontmatter")
    parser.add_argument("--mode", type=str, help='Mode for frontmatter (e.g., "wide")')

    # Processing options
    parser.add_argument(
        "--download-assets",
        action="store_true",
        help="Copy local image assets to /images (the default when converting a directory)",
    )
    parser.add_argument(
        "--no-assets",
        action="store_true",
        help="Do not copy images; leave their paths as written",
    )
    parser.add_argument(
        "--static-dir",
        type=str,
        help="Docusaurus static folder that '/img/...' paths resolve against "
        "(default: ../static or ./static next to the docs)",
    )
    parser.add_argument(
        "--site-url",
        type=str,
        help="Base URL of the original site (https://docusaurus.io). Links to pages outside the "
        "docs, such as /blog or /community, become absolute links to it",
    )
    parser.add_argument(
        "--route-prefix",
        type=str,
        help="URL prefix the source site served its docs under, removed from links "
        "(default: /docs when the input folder is named docs)",
    )
    parser.add_argument(
        "--validate", action="store_true", help="Validate MDX output and report errors"
    )
    parser.add_argument("--verbose", action="store_true", help="Show detailed error messages")

    # Navigation options
    parser.add_argument(
        "--generate-config",
        action="store_true",
        help="Generate docs.json (navigation and branding) in the output directory",
    )
    parser.add_argument(
        "--legacy-mint-json",
        action="store_true",
        help="With --generate-config, write the legacy mint.json instead of docs.json",
    )
    parser.add_argument(
        "--generate-mint-json",
        action="store_true",
        help="Deprecated alias for --generate-config --legacy-mint-json",
    )
    parser.add_argument(
        "--structure",
        choices=("diataxis", "folders"),
        default="diataxis",
        help="Navigation layout: 'diataxis' (default) sorts pages into Get started, Tutorials, "
        "How-to guides and Concepts with API reference in its own tab; 'folders' mirrors the "
        "source folders",
    )
    parser.add_argument(
        "--ia-config",
        type=str,
        help="JSON file that moves pages between sections, renames groups and tabs",
    )
    parser.add_argument(
        "--explain-ia",
        action="store_true",
        help="Print the section chosen for each page and why",
    )
    parser.add_argument(
        "--sort-pages", action="store_true", help="Sort pages alphabetically within groups"
    )
    parser.add_argument(
        "--project-name",
        type=str,
        default="Documentation",
        help="Project name for the generated config",
    )

    # Branding options
    parser.add_argument("--primary-color", type=str, help="Primary brand color")
    parser.add_argument("--light-color", type=str, help="Light brand color")
    parser.add_argument("--dark-color", type=str, help="Dark brand color")
    parser.add_argument("--support-url", type=str, help="Support URL for topbar")
    parser.add_argument("--dashboard-url", type=str, help="Dashboard URL for CTA button")
    parser.add_argument("--twitter", type=str, help="Twitter URL")
    parser.add_argument("--github", type=str, help="GitHub URL")
    parser.add_argument("--linkedin", type=str, help="LinkedIn URL")

    args = parser.parse_args(argv)

    if args.generate_mint_json:
        print(
            "Warning: --generate-mint-json is deprecated; use --generate-config --legacy-mint-json",
            file=sys.stderr,
        )
        args.generate_config = True
        args.legacy_mint_json = True
    if args.legacy_mint_json and not args.generate_config:
        parser.error("--legacy-mint-json requires --generate-config")

    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: {input_path} does not exist", file=sys.stderr)
        sys.exit(1)

    kwargs = vars(args)
    ia_config = None
    if args.ia_config:
        try:
            ia_config = ia.load_ia_config(args.ia_config)
        except (OSError, ValueError) as e:
            print(f"Error: cannot read --ia-config: {e}", file=sys.stderr)
            sys.exit(1)

    if input_path.is_file():
        output_path = Path(args.output) if args.output else None
        if output_path is not None and output_path.is_dir():
            output_path = output_path / input_path.name
        if args.generate_config:
            print(
                "Warning: --generate-config only applies to directory conversion; ignoring",
                file=sys.stderr,
            )
        for flag in ("static_dir", "site_url", "route_prefix"):
            if getattr(args, flag):
                print(
                    f"Warning: --{flag.replace('_', '-')} only applies to directory conversion; "
                    "ignoring",
                    file=sys.stderr,
                )
        success, _ = process_file(input_path, output_path, **kwargs)
        if not success:
            sys.exit(1)
    else:
        if not args.output:
            print("Error: Output directory required for directory conversion", file=sys.stderr)
            sys.exit(1)

        output_dir = Path(args.output)
        problem = check_paths(input_path, output_dir)
        if problem:
            print(f"Error: {problem}", file=sys.stderr)
            sys.exit(1)

        # Images are copied by default for a directory so the Frames never point at missing files.
        kwargs["download_assets"] = not args.no_assets
        file_metadata = process_directory(input_path, output_dir, **kwargs)

        if args.generate_config and not file_metadata:
            print("Warning: no pages were converted, so no config was written", file=sys.stderr)
        if args.generate_config and file_metadata:
            nav_names = (
                "project_name",
                "primary_color",
                "light_color",
                "dark_color",
                "support_url",
                "dashboard_url",
                "twitter",
                "github",
                "linkedin",
                "sort_pages",
            )
            nav_kwargs = {k: kwargs[k] for k in nav_names if kwargs.get(k) is not None}
            try:
                if not args.legacy_mint_json:
                    nav_kwargs.update(
                        structure=args.structure,
                        ia_config=ia_config,
                        categories=getattr(file_metadata, "categories", None),
                        redirects=getattr(file_metadata, "redirects", None),
                    )
                if args.legacy_mint_json:
                    generate_enhanced_mint_json(
                        file_metadata, output_dir / "mint.json", **nav_kwargs
                    )
                else:
                    generate_docs_json(file_metadata, output_dir / "docs.json", **nav_kwargs)
            except (ValueError, OSError) as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
            if args.explain_ia:
                print("\nSection chosen for each page:")
                print("\n".join(ia.describe_decisions(file_metadata)))

        if args.validate and file_metadata:
            problems = check_site(output_dir)
            if problems:
                print(f"\n\u26a0 {len(problems)} problem(s) in the converted site:")
                for problem in problems:
                    print(f"  - {problem}")
            else:
                print("\n\u2713 All internal links, anchors, images and navigation entries resolve")

        converted = getattr(file_metadata, "converted", len(file_metadata))
        if converted < len(find_mdx_files(input_path)):
            sys.exit(1)


if __name__ == "__main__":
    main()
