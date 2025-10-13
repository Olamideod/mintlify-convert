#!/usr/bin/env python3
"""
Mintlify Convert - Standalone Version
Single file, no installation needed!

Usage:
    python mintlify_convert.py input.mdx -o output.mdx
    python mintlify_convert.py docs/ -o mintlify-docs/ --generate-mint-json
"""

import re
import sys
import argparse
import os
import shutil
import json
from pathlib import Path
from typing import Dict, List, Optional

# ============================================================================
# CONVERTER CLASS
# ============================================================================

class MintlifyConverter:
    """Main converter class for MDX to Mintlify transformation"""
    
    def __init__(self, output_dir: Path = None, download_assets: bool = False):
        self.output_dir = output_dir
        self.download_assets = download_assets
        self.assets_copied = {}
        self.validation_errors = []
        
    def extract_title(self, content: str) -> str:
        """Extract title from first H1 heading"""
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        return match.group(1).strip() if match else "Untitled"
    
    def extract_description(self, content: str) -> str:
        """Extract description from first paragraph after title"""
        without_title = re.sub(r'^#\s+.+\n+', '', content, count=1)
        match = re.search(r'^(.+?)(?:\n\n|$)', without_title, re.DOTALL)
        if match:
            desc = match.group(1).strip()
            desc = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', desc)
            desc = re.sub(r'\*\*(.+?)\*\*', r'\1', desc)
            desc = desc.replace('\n', ' ')
            return desc[:200] + '...' if len(desc) > 200 else desc
        return ""
    
    def convert_callouts(self, content: str) -> str:
        """Convert blockquotes to Mintlify Callout components"""
        lines = content.split('\n')
        result = []
        in_callout = False
        callout_lines = []
        
        for line in lines:
            if line.strip().startswith('>'):
                if not in_callout:
                    in_callout = True
                    callout_lines = []
                callout_lines.append(line.strip()[1:].strip())
            else:
                if in_callout and callout_lines:
                    callout_text = '\n'.join(callout_lines)
                    callout_type = self._determine_callout_type(callout_text)
                    result.append(f'<Callout type="{callout_type}">')
                    result.append(callout_text)
                    result.append('</Callout>')
                    in_callout = False
                    callout_lines = []
                result.append(line)
        
        if in_callout and callout_lines:
            callout_text = '\n'.join(callout_lines)
            callout_type = self._determine_callout_type(callout_text)
            result.append(f'<Callout type="{callout_type}">')
            result.append(callout_text)
            result.append('</Callout>')
        
        return '\n'.join(result)
    
    def _determine_callout_type(self, text: str) -> str:
        """Determine appropriate callout type"""
        text_lower = text.lower()
        if any(word in text_lower for word in ['warning', 'caution', 'critical']):
            return 'warning'
        elif any(word in text_lower for word in ['tip', 'hint']):
            return 'tip'
        elif any(word in text_lower for word in ['note', 'remember']):
            return 'note'
        return 'info'
    
    def convert_numbered_steps(self, content: str) -> str:
        """Convert numbered lists to Steps component"""
        lines = content.split('\n')
        result = []
        in_steps = False
        steps = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            match = re.match(r'^\s*(\d+)\.\s+(.+)$', line)
            
            if match:
                if not in_steps:
                    in_steps = True
                    steps = []
                
                step_content = [match.group(2)]
                i += 1
                while i < len(lines) and lines[i].strip() and not re.match(r'^\s*\d+\.', lines[i]):
                    step_content.append(lines[i])
                    i += 1
                steps.append('\n'.join(step_content))
                continue
            else:
                if in_steps and steps:
                    result.append('<Steps>')
                    for idx, step in enumerate(steps, 1):
                        result.append(f'  <Step title="Step {idx}">')
                        result.append(f'  {step}')
                        result.append('  </Step>')
                    result.append('</Steps>')
                    in_steps = False
                    steps = []
                result.append(line)
            i += 1
        
        if in_steps and steps:
            result.append('<Steps>')
            for idx, step in enumerate(steps, 1):
                result.append(f'  <Step title="Step {idx}">')
                result.append(f'  {step}')
                result.append('  </Step>')
            result.append('</Steps>')
        
        return '\n'.join(result)
    
    def convert_tabs(self, content: str) -> str:
        """Convert language-labeled sections to Tabs"""
        lines = content.split('\n')
        result = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            tab_indicator = re.match(r'^(JavaScript|Python|TypeScript|Ruby|Go|Java|PHP|Curl):\s*$', 
                                    line.strip(), re.IGNORECASE)
            
            if tab_indicator:
                tabs = []
                current_lang = tab_indicator.group(1)
                content_lines = []
                i += 1
                
                while i < len(lines):
                    next_tab = re.match(r'^(JavaScript|Python|TypeScript|Ruby|Go|Java|PHP|Curl):\s*$',
                                       lines[i].strip(), re.IGNORECASE)
                    
                    if next_tab:
                        if content_lines:
                            tabs.append((current_lang, '\n'.join(content_lines).strip()))
                        current_lang = next_tab.group(1)
                        content_lines = []
                        i += 1
                    elif not lines[i].strip() and tabs:
                        break
                    else:
                        content_lines.append(lines[i])
                        i += 1
                
                if content_lines:
                    tabs.append((current_lang, '\n'.join(content_lines).strip()))
                
                if len(tabs) > 1:
                    result.append('<Tabs>')
                    for lang, code in tabs:
                        result.append(f'  <Tab title="{lang}">')
                        if '```' not in code:
                            result.append(f'```{lang.lower()}')
                            result.append(code)
                            result.append('```')
                        else:
                            result.append(code)
                        result.append('  </Tab>')
                    result.append('</Tabs>')
                    continue
            
            result.append(line)
            i += 1
        
        return '\n'.join(result)
    
    def convert_help_sections(self, content: str) -> str:
        """Convert help sections to Card components"""
        pattern = r'^(Need help\?|Questions\?|Support|Contact us)\s*\n+(.*?)(?=\n\n|\Z)'
        
        def replacer(match):
            title = match.group(1)
            text = match.group(2).strip()
            return f'<Card title="{title}" icon="question">\n  {text}\n</Card>'
        
        return re.sub(pattern, replacer, content, flags=re.MULTILINE | re.DOTALL)
    
    def convert_api_links(self, content: str) -> str:
        """Convert API reference links"""
        pattern = r'\[(.+?)\]\(/api/#operation/([^)]+)\)'
        return re.sub(pattern, r'[\1](/api-reference/\2)', content)
    
    def create_frontmatter(self, title: str, description: str = "", 
                          icon: str = "", mode: str = "") -> str:
        """Create Mintlify frontmatter"""
        fm = ['---']
        fm.append(f'title: "{title}"')
        if description:
            description = description.replace('"', '\\"')
            fm.append(f'description: "{description}"')
        if icon:
            fm.append(f'icon: "{icon}"')
        if mode:
            fm.append(f'mode: "{mode}"')
        fm.append('---')
        return '\n'.join(fm)
    
    def remove_original_title(self, content: str) -> str:
        """Remove first H1 heading"""
        return re.sub(r'^#\s+.+\n+', '', content, count=1)
    
    def convert(self, mdx_content: str, source_file: Path = None, **kwargs) -> str:
        """Main conversion method"""
        title = self.extract_title(mdx_content)
        description = self.extract_description(mdx_content)
        
        result = self.create_frontmatter(
            title, 
            description, 
            icon=kwargs.get('icon', ''),
            mode=kwargs.get('mode', '')
        )
        result += '\n\n'
        
        content = self.remove_original_title(mdx_content)
        content = self.convert_api_links(content)
        content = self.convert_numbered_steps(content)
        content = self.convert_tabs(content)
        content = self.convert_callouts(content)
        content = self.convert_help_sections(content)
        
        result += content
        return result


# ============================================================================
# NAVIGATION GENERATION
# ============================================================================

def generate_mint_json(file_metadata: Dict, output_path: Path, **kwargs):
    """Generate mint.json navigation file"""
    groups = {}
    
    for file_path, meta in sorted(file_metadata.items()):
        group_name = meta['group']
        if group_name not in groups:
            groups[group_name] = []
        groups[group_name].append(meta['path'])
    
    navigation = []
    for group_name, pages in sorted(groups.items()):
        group_title = group_name.replace('-', ' ').replace('_', ' ').title()
        navigation.append({'group': group_title, 'pages': pages})
    
    mint_config = {
        'name': kwargs.get('project_name', 'Documentation'),
        'logo': {'dark': '/logo/dark.svg', 'light': '/logo/light.svg'},
        'favicon': '/favicon.svg',
        'colors': {
            'primary': kwargs.get('primary_color', '#0D9373'),
            'light': kwargs.get('light_color', '#07C983'),
            'dark': kwargs.get('dark_color', '#0D9373')
        },
        'navigation': navigation
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(mint_config, f, indent=2)
    
    print(f"✓ Generated mint.json at {output_path}")


# ============================================================================
# FILE PROCESSING
# ============================================================================

def process_file(input_path: Path, output_path: Path = None, 
                converter: MintlifyConverter = None, **kwargs):
    """Process a single MDX file"""
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if converter is None:
            converter = MintlifyConverter()
        
        converted = converter.convert(content, source_file=input_path, **kwargs)
        
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(converted)
            print(f"✓ Converted: {input_path} -> {output_path}")
        else:
            print(converted)
        
        return True, converter.extract_title(content)
    except Exception as e:
        print(f"✗ Error: {str(e)}", file=sys.stderr)
        return False, None


def process_directory(input_dir: Path, output_dir: Path, **kwargs):
    """Process all MDX files in a directory"""
    mdx_files = list(input_dir.rglob('*.mdx')) + list(input_dir.rglob('*.md'))
    
    if not mdx_files:
        print(f"No MDX/MD files found in {input_dir}")
        return {}
    
    print(f"Found {len(mdx_files)} files to convert...")
    
    converter = MintlifyConverter(output_dir)
    file_metadata = {}
    success_count = 0
    
    for mdx_file in mdx_files:
        relative_path = mdx_file.relative_to(input_dir)
        output_path = output_dir / relative_path
        
        success, title = process_file(mdx_file, output_path, converter, **kwargs)
        if success:
            success_count += 1
            file_metadata[str(relative_path.with_suffix(''))] = {
                'title': title,
                'path': str(relative_path.with_suffix('')),
                'group': str(relative_path.parent) if relative_path.parent != Path('.') else 'Documentation'
            }
    
    print(f"\n✓ Successfully converted {success_count}/{len(mdx_files)} files")
    return file_metadata


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Convert MDX files to Mintlify format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python mintlify_convert.py input.mdx -o output.mdx
  python mintlify_convert.py docs/ -o mintlify-docs/ --generate-mint-json
        """
    )
    
    parser.add_argument('input', help='Input MDX file or directory')
    parser.add_argument('-o', '--output', help='Output file or directory')
    parser.add_argument('--generate-mint-json', action='store_true',
                       help='Generate mint.json navigation file')
    parser.add_argument('--icon', help='Icon for frontmatter')
    parser.add_argument('--mode', help='Mode for frontmatter')
    parser.add_argument('--project-name', default='Documentation',
                       help='Project name for mint.json')
    parser.add_argument('--primary-color', default='#0D9373',
                       help='Primary brand color')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if not input_path.exists():
        print(f"Error: {input_path} does not exist", file=sys.stderr)
        sys.exit(1)
    
    kwargs = vars(args)
    
    if input_path.is_file():
        output_path = Path(args.output) if args.output else None
        success, _ = process_file(input_path, output_path, **kwargs)
        sys.exit(0 if success else 1)
    else:
        if not args.output:
            print("Error: Output directory required", file=sys.stderr)
            sys.exit(1)
        
        output_dir = Path(args.output)
        file_metadata = process_directory(input_path, output_dir, **kwargs)
        
        if args.generate_mint_json and file_metadata:
            generate_mint_json(file_metadata, output_dir / 'mint.json', **kwargs)


if __name__ == '__main__':
    main()