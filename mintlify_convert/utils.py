#!/usr/bin/env python3
"""
Utility functions for Mintlify Convert.
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from .converter import MintlifyConverter


def process_file(input_path: Path, output_path: Path = None, 
                converter: MintlifyConverter = None, **kwargs) -> Tuple[bool, Optional[str]]:
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
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if converter is None:
            converter = MintlifyConverter(output_path.parent if output_path else None)
        
        converted = converter.convert(content, source_file=input_path, **kwargs)
        
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(converted)
            
            # Report validation errors
            if kwargs.get('validate') and converter.validation_errors:
                print(f"⚠ Validation warnings for {input_path}:")
                for error in converter.validation_errors:
                    print(f"  - {error}")
            else:
                print(f"✓ Converted: {input_path} -> {output_path}")
        else:
            print(converted)
        
        return True, converter.extract_title(content)
    except Exception as e:
        print(f"✗ Error processing {input_path}: {str(e)}", file=sys.stderr)
        if kwargs.get('verbose'):
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
    """
    mdx_files = list(input_dir.rglob('*.mdx')) + list(input_dir.rglob('*.md'))
    
    if not mdx_files:
        print(f"No MDX/MD files found in {input_dir}")
        return {}
    
    print(f"Found {len(mdx_files)} files to convert...")
    
    converter = MintlifyConverter(output_dir, download_assets=kwargs.get('download_assets', False))
    success_count = 0
    file_metadata = {}
    
    for mdx_file in mdx_files:
        relative_path = mdx_file.relative_to(input_dir)
        output_path = output_dir / relative_path
        
        success, title = process_file(mdx_file, output_path, converter, **kwargs)
        if success:
            success_count += 1
            # Store metadata for navigation
            file_metadata[str(relative_path.with_suffix(''))] = {
                'title': title,
                'path': str(relative_path.with_suffix('')),
                'group': str(relative_path.parent) if relative_path.parent != Path('.') else 'Documentation'
            }
    
    print(f"\n✓ Successfully converted {success_count}/{len(mdx_files)} files")
    
    if converter.assets_copied:
        print(f"✓ Copied {len(converter.assets_copied)} assets to /images")
    
    return file_metadata


def find_mdx_files(directory: Path) -> List[Path]:
    """Find all MDX and MD files in a directory.
    
    Args:
        directory: Directory to search
        
    Returns:
        List of MDX/MD file paths
    """
    return list(directory.rglob('*.mdx')) + list(directory.rglob('*.md'))


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
    
    if input_path.is_file() and not input_path.suffix.lower() in ['.md', '.mdx']:
        print(f"Error: {input_path} is not an MDX or MD file", file=sys.stderr)
        return False
    
    return True


def print_conversion_summary(converted_count: int, total_count: int, 
                           assets_copied: int = 0, errors: list = None) -> None:
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
