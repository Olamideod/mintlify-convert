#!/usr/bin/env python3
"""
Command-line interface for Mintlify Convert.
"""

import argparse
import sys
from pathlib import Path
from typing import Dict

from .converter import MintlifyConverter
from .utils import process_file, process_directory
from .navigation import generate_enhanced_mint_json


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Convert MDX files to Mintlify format (v2 - Enhanced)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert a single file
  mintlify-convert input.mdx -o output.mdx
  
  # Convert a directory with assets
  mintlify-convert docs/ -o mintlify-docs/ --download-assets
  
  # Generate enhanced mint.json
  mintlify-convert docs/ -o mintlify-docs/ --generate-mint-json --sort-pages
  
  # Validate output
  mintlify-convert docs/ -o mintlify-docs/ --validate
  
  # Full conversion with all features
  mintlify-convert docs/ -o mintlify-docs/ \\
    --generate-mint-json \\
    --download-assets \\
    --validate \\
    --sort-pages \\
    --project-name "My API Docs"
        """
    )
    
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument('--url', type=str, help='Live URL to scrape and convert')
    src.add_argument('input', nargs='?', help='Input MDX file or directory')

    parser.add_argument('-o', '--output', type=str, help='Output file or directory')
    
    # Frontmatter options
    parser.add_argument('--icon', type=str, help='Icon for frontmatter')
    parser.add_argument('--mode', type=str, help='Mode for frontmatter (e.g., "wide")')
    
    # Processing options
    parser.add_argument('--download-assets', action='store_true',
                       help='Download and copy image assets to /images')
    parser.add_argument('--validate', action='store_true',
                       help='Validate MDX output and report errors')
    parser.add_argument('--use-ai-description', action='store_true',
                       help='Use AI to generate descriptions (requires OpenAI API key)')
    parser.add_argument('--verbose', action='store_true',
                       help='Show detailed error messages')
    
    # Navigation options
    parser.add_argument('--generate-mint-json', action='store_true',
                       help='Generate mint.json navigation file')
    parser.add_argument('--sort-pages', action='store_true',
                       help='Sort pages alphabetically within groups')
    parser.add_argument('--project-name', type=str, default='Documentation',
                       help='Project name for mint.json')
    
    # Branding options
    parser.add_argument('--primary-color', type=str, default='#0D9373',
                       help='Primary brand color')
    parser.add_argument('--light-color', type=str, default='#07C983',
                       help='Light brand color')
    parser.add_argument('--dark-color', type=str, default='#0D9373',
                       help='Dark brand color')
    parser.add_argument('--support-url', type=str,
                       help='Support URL for topbar')
    parser.add_argument('--dashboard-url', type=str,
                       help='Dashboard URL for CTA button')
    parser.add_argument('--twitter', type=str, help='Twitter URL')
    parser.add_argument('--github', type=str, help='GitHub URL')
    parser.add_argument('--linkedin', type=str, help='LinkedIn URL')
    
    args = parser.parse_args()

    kwargs = vars(args)

    # URL flow: scrape then convert
    if args.url:
        if not args.output:
            print("Error: Output directory required when using --url", file=sys.stderr)
            sys.exit(1)
        from .scraper import scrape_url_to_mdx
        output_dir = Path(args.output)
        mdx_path, _content = scrape_url_to_mdx(args.url, output_dir)
        # Convert the produced MDX into Mintlify format (overwrite in place)
        success, title = process_file(mdx_path, mdx_path, **kwargs)
        if args.generate_mint_json:
            rel = mdx_path.with_suffix('').relative_to(output_dir)
            file_metadata = {str(rel): {
                'title': title or mdx_path.stem,
                'path': str(rel),
                'group': 'Documentation'
            }}
            generate_enhanced_mint_json(file_metadata, output_dir / 'mint.json', **kwargs)
        sys.exit(0)

    # File/dir flow
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: {input_path} does not exist", file=sys.stderr)
        sys.exit(1)

    if input_path.is_file():
        output_path = Path(args.output) if args.output else None
        process_file(input_path, output_path, **kwargs)
    else:
        if not args.output:
            print("Error: Output directory required for directory conversion", file=sys.stderr)
            sys.exit(1)

        output_dir = Path(args.output)
        file_metadata = process_directory(input_path, output_dir, **kwargs)

        if args.generate_mint_json and file_metadata:
            generate_enhanced_mint_json(file_metadata, output_dir / 'mint.json', **kwargs)


if __name__ == '__main__':
    main()
