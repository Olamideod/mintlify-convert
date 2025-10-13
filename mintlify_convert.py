#!/usr/bin/env python3
"""
MDX to Mintlify Format Converter v2
Enhanced with Phase 2 features:
- Additional Mintlify components (Accordion, Tabs, Banner, Callout)
- Enhanced navigation with nested groups
- Asset handling and link rewriting
- MDX validation
- AI description generation (optional)
"""

import re
import sys
import argparse
import os
import shutil
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from urllib.parse import urlparse, urljoin
import hashlib


class MintlifyConverter:
    def __init__(self, output_dir: Path = None, download_assets: bool = False):
        self.frontmatter = {}
        self.content_lines = []
        self.output_dir = output_dir
        self.download_assets = download_assets
        self.assets_copied = {}
        self.validation_errors = []
        
    def extract_title(self, content: str) -> str:
        """Extract title from first H1 heading."""
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        return match.group(1).strip() if match else "Untitled"
    
    def extract_description(self, content: str) -> str:
        """Extract description from first paragraph after title."""
        without_title = re.sub(r'^#\s+.+\n+', '', content, count=1)
        match = re.search(r'^(.+?)(?:\n\n|$)', without_title, re.DOTALL)
        if match:
            desc = match.group(1).strip()
            desc = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', desc)
            desc = re.sub(r'\*\*(.+?)\*\*', r'\1', desc)
            desc = desc.replace('\n', ' ')
            return desc[:200] + '...' if len(desc) > 200 else desc
        return ""
    
    def generate_ai_description(self, content: str) -> str:
        """Generate description using AI (placeholder for OpenAI integration)."""
        # TODO: Integrate with OpenAI API
        # For now, return extracted description
        return self.extract_description(content)
    
    def convert_api_links(self, content: str) -> str:
        """Convert API reference links to Mintlify format."""
        pattern = r'\[(.+?)\]\(/api/#operation/([^)]+)\)'
        replacement = r'[\1](/api-reference/\2)'
        return re.sub(pattern, replacement, content)
    
    def convert_relative_links(self, content: str, current_file: Path = None) -> str:
        """Convert relative links to correct Mintlify paths."""
        def replace_link(match):
            text = match.group(1)
            url = match.group(2)
            
            # Skip external links
            if url.startswith(('http://', 'https://', 'mailto:', '#')):
                return match.group(0)
            
            # Convert .md/.mdx links
            if url.endswith(('.md', '.mdx')):
                url = url.rsplit('.', 1)[0]
            
            # Convert relative paths
            if current_file and not url.startswith('/'):
                # Make path relative to docs root
                url = '/' + url
            
            return f'[{text}]({url})'
        
        pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        return re.sub(pattern, replace_link, content)
    
    def handle_images(self, content: str, source_file: Path = None) -> str:
        """Handle image links - copy to assets and update paths following technical writing rules."""
        def replace_image(match):
            alt = match.group(1)
            src = match.group(2)
            
            # Skip external images
            if src.startswith(('http://', 'https://')):
                return match.group(0)
            
            # Handle local images
            if source_file and self.output_dir:
                source_img_path = source_file.parent / src
                if source_img_path.exists():
                    # Create assets directory
                    assets_dir = self.output_dir / 'images'
                    assets_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Copy image with unique name if needed
                    img_name = source_img_path.name
                    dest_path = assets_dir / img_name
                    
                    # Handle name conflicts
                    counter = 1
                    while dest_path.exists() and dest_path not in self.assets_copied.values():
                        name, ext = os.path.splitext(img_name)
                        dest_path = assets_dir / f"{name}_{counter}{ext}"
                        counter += 1
                    
                    if source_img_path not in self.assets_copied:
                        shutil.copy2(source_img_path, dest_path)
                        self.assets_copied[source_img_path] = dest_path
                    
                    # Wrap images in Frame component following technical writing rules
                    return self._wrap_image_in_frame(alt, f'/images/{dest_path.name}')
            
            return match.group(0)
        
        # Match both markdown and HTML image syntax
        content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_image, content)
        content = re.sub(r'<img\s+src="([^"]+)"(?:\s+alt="([^"]*)")?\s*/?>', 
                        lambda m: replace_image(type('obj', (), {'group': lambda i: m.group(2) if i == 1 else m.group(1)})()),
                        content)
        
        return content
    
    def _wrap_image_in_frame(self, alt: str, src: str) -> str:
        """Wrap image in Frame component following technical writing rules."""
        # Ensure descriptive alt text following accessibility requirements
        if not alt or alt.strip() == '':
            alt = "Documentation image"
        
        # Create proper Frame component
        return f'<Frame>\n  <img src="{src}" alt="{alt}" />\n</Frame>'
    
    def convert_callouts(self, content: str) -> str:
        """Convert blockquotes to Mintlify Callout components following technical writing rules."""
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
                    # Use proper Mintlify component names following technical writing rules
                    component_name = self._get_proper_callout_component(callout_type)
                    result.append(f'<{component_name}>')
                    result.append(callout_text)
                    result.append(f'</{component_name}>')
                    in_callout = False
                    callout_lines = []
                
                result.append(line)
        
        if in_callout and callout_lines:
            callout_text = '\n'.join(callout_lines)
            callout_type = self._determine_callout_type(callout_text)
            component_name = self._get_proper_callout_component(callout_type)
            result.append(f'<{component_name}>')
            result.append(callout_text)
            result.append(f'</{component_name}>')
        
        return '\n'.join(result)
    
    def _determine_callout_type(self, text: str) -> str:
        """Determine the appropriate callout type following Mintlify technical writing rules."""
        text_lower = text.lower()
        if any(word in text_lower for word in ['warning', 'caution', 'critical', 'danger', 'important']):
            return 'warning'
        elif any(word in text_lower for word in ['tip', 'hint', 'best practice', 'pro tip']):
            return 'tip'
        elif any(word in text_lower for word in ['note', 'remember', 'additional']):
            return 'note'
        elif any(word in text_lower for word in ['success', 'complete', 'done', 'achieved']):
            return 'check'
        else:
            return 'info'
    
    def _get_proper_callout_component(self, callout_type: str) -> str:
        """Get the proper Mintlify component name following technical writing rules."""
        component_map = {
            'warning': 'Warning',
            'tip': 'Tip', 
            'note': 'Note',
            'info': 'Info',
            'check': 'Check'
        }
        return component_map.get(callout_type, 'Info')
    
    def convert_banner(self, content: str) -> str:
        """Convert top-level important notices to Banner components."""
        # Match patterns like "⚠️ Important:" or "🚨 Deprecated:"
        pattern = r'^(?:[⚠️🚨📢💡]\s*)?(Deprecated|Important|Notice|Alert)[:\s]+(.+?)(?=\n\n|##|\Z)'
        
        def replacer(match):
            banner_type = match.group(1).lower()
            text = match.group(2).strip()
            
            # Map to banner types
            type_map = {
                'deprecated': 'warning',
                'important': 'warning',
                'notice': 'info',
                'alert': 'warning'
            }
            
            return f'<Banner type="{type_map.get(banner_type, "info")}">\n  {text}\n</Banner>'
        
        return re.sub(pattern, replacer, content, flags=re.MULTILINE | re.DOTALL)
    
    def convert_accordions(self, content: str) -> str:
        """Convert H2/H3 sections with collapsible content to Accordion following technical writing rules."""
        lines = content.split('\n')
        result = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Check if this looks like an accordion section following technical writing rules
            h3_match = re.match(r'^###\s+(.+)$', line)
            
            if h3_match and i > 0:
                # Look ahead to see if we should make this an accordion
                title = h3_match.group(1)
                content_lines = []
                i += 1
                
                # Collect content until next heading or double newline
                while i < len(lines) and not re.match(r'^#{1,3}\s+', lines[i]):
                    if lines[i].strip():
                        content_lines.append(lines[i])
                    elif content_lines:  # Empty line after content
                        break
                    i += 1
                
                # Determine if this should be an accordion based on content type and length
                if self._should_be_accordion(title, content_lines):
                    # Use AccordionGroup for multiple related accordions, single Accordion for standalone
                    result.append(f'<Accordion title="{title}">')
                    result.extend(content_lines)
                    result.append('</Accordion>')
                else:
                    # Keep as regular heading
                    result.append(line)
                    result.extend(content_lines)
                
                continue
            
            result.append(line)
            i += 1
        
        return '\n'.join(result)
    
    def _should_be_accordion(self, title: str, content_lines: list) -> bool:
        """Determine if content should be converted to accordion following technical writing rules."""
        title_lower = title.lower()
        
        # Accordion-worthy sections based on technical writing best practices
        accordion_keywords = [
            'troubleshooting', 'faq', 'advanced', 'configuration', 'options',
            'examples', 'reference', 'details', 'breakdown', 'break down',
            'step by step', 'walkthrough', 'common issues', 'error codes',
            'parameters', 'settings', 'environment', 'deployment'
        ]
        
        # Check if title suggests accordion content
        if any(keyword in title_lower for keyword in accordion_keywords):
            return True
            
        # Check content length and complexity
        content_text = '\n'.join(content_lines)
        if len(content_lines) >= 3 and (len(content_text) > 200 or '```' in content_text):
            return True
            
        return False
    
    def convert_tabs(self, content: str) -> str:
        """Convert code blocks or sections marked for different languages into Tabs following technical writing rules."""
        
        def find_tab_groups(text):
            """Find consecutive code blocks that should be tabs."""
            lines = text.split('\n')
            result = []
            i = 0
            
            while i < len(lines):
                line = lines[i]
                
                # Check for tab indicators like "JavaScript:" or "Python:" following technical writing rules
                tab_indicator = re.match(r'^(JavaScript|Python|TypeScript|Ruby|Go|Java|PHP|Curl|Node\.js|React|Vue|Angular|Bash|Shell|PowerShell):\s*$', line.strip(), re.IGNORECASE)
                
                if tab_indicator:
                    # Start collecting tabs
                    tabs = []
                    current_lang = tab_indicator.group(1)
                    content_lines = []
                    i += 1
                    
                    while i < len(lines):
                        # Check for next tab or end
                        next_tab = re.match(r'^(JavaScript|Python|TypeScript|Ruby|Go|Java|PHP|Curl|Node\.js|React|Vue|Angular|Bash|Shell|PowerShell):\s*$', lines[i].strip(), re.IGNORECASE)
                        
                        if next_tab:
                            # Save current tab
                            if content_lines:
                                tabs.append((current_lang, '\n'.join(content_lines).strip()))
                            current_lang = next_tab.group(1)
                            content_lines = []
                            i += 1
                        elif not lines[i].strip() and tabs:
                            # Empty line might signal end
                            break
                        else:
                            content_lines.append(lines[i])
                            i += 1
                    
                    # Save last tab
                    if content_lines:
                        tabs.append((current_lang, '\n'.join(content_lines).strip()))
                    
                    # Generate tab component following technical writing rules
                    if len(tabs) > 1:
                        result.append('<Tabs>')
                        for lang, code in tabs:
                            # Use proper language display names
                            display_name = self._get_proper_language_name(lang)
                            result.append(f'  <Tab title="{display_name}">')
                            # Ensure proper code block formatting
                            if code.strip().startswith('```'):
                                result.append(code)
                            else:
                                result.append(f'```{lang.lower()}')
                                result.append(code)
                                result.append('```')
                            result.append('  </Tab>')
                        result.append('</Tabs>')
                        continue
                
                result.append(line)
                i += 1
            
            return '\n'.join(result)
        
        return find_tab_groups(content)
    
    def _get_proper_language_name(self, lang: str) -> str:
        """Get proper display name for programming languages following technical writing rules."""
        language_map = {
            'javascript': 'JavaScript',
            'python': 'Python',
            'typescript': 'TypeScript',
            'ruby': 'Ruby',
            'go': 'Go',
            'java': 'Java',
            'php': 'PHP',
            'curl': 'cURL',
            'node.js': 'Node.js',
            'react': 'React',
            'vue': 'Vue.js',
            'angular': 'Angular',
            'bash': 'Bash',
            'shell': 'Shell',
            'powershell': 'PowerShell'
        }
        return language_map.get(lang.lower(), lang)
    
    def convert_lists_with_bold_headers(self, content: str) -> str:
        """Convert lists with bold headers to better structured format."""
        pattern = r'^\s*[\*\-]\s+\*\*(.+?)\*\*\s+(.+)$'
        
        def replacer(match):
            header = match.group(1)
            description = match.group(2)
            return f'* **{header}**: {description}'
        
        return re.sub(pattern, replacer, content, flags=re.MULTILINE)
    
    def convert_numbered_steps(self, content: str) -> str:
        """Convert numbered lists to Mintlify Steps component following technical writing rules."""
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
                        # Extract meaningful title from step content
                        step_title = self._extract_step_title(step)
                        result.append(f'  <Step title="{step_title}">')
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
                step_title = self._extract_step_title(step)
                result.append(f'  <Step title="{step_title}">')
                result.append(f'  {step}')
                result.append('  </Step>')
            result.append('</Steps>')
        
        return '\n'.join(result)
    
    def _extract_step_title(self, step_content: str) -> str:
        """Extract a meaningful title from step content following technical writing rules."""
        # Take the first line and clean it up for use as a title
        first_line = step_content.split('\n')[0].strip()
        # Remove common prefixes and clean up
        first_line = re.sub(r'^(First|Next|Then|Finally|Step \d+:?)\s*', '', first_line, flags=re.IGNORECASE)
        # Limit length and ensure it's descriptive
        if len(first_line) > 60:
            first_line = first_line[:57] + "..."
        return first_line or "Step"
    
    def convert_help_sections(self, content: str) -> str:
        """Convert 'Need help?' or similar sections to Card components following technical writing rules."""
        # Enhanced pattern to catch more help section variations
        pattern = r'^(Need help\?|Questions\?|Support|Contact us|Get help|Need assistance|Stuck\?|Having trouble\?)\s*\n+(.*?)(?=\n\n|\Z)'
        
        def replacer(match):
            title = match.group(1)
            text = match.group(2).strip()
            
            # Choose appropriate icon based on content following technical writing rules
            icon = self._get_help_section_icon(title, text)
            
            # Clean up the text for better presentation
            cleaned_text = self._clean_help_section_text(text)
            
            return f'<Card title="{title}" icon="{icon}">\n  {cleaned_text}\n</Card>'
        
        return re.sub(pattern, replacer, content, flags=re.MULTILINE | re.DOTALL)
    
    def _get_help_section_icon(self, title: str, text: str) -> str:
        """Get appropriate icon for help section following technical writing rules."""
        title_lower = title.lower()
        text_lower = text.lower()
        
        if any(word in title_lower for word in ['support', 'contact']):
            return 'headphones'
        elif any(word in title_lower for word in ['questions', 'stuck', 'trouble']):
            return 'question'
        elif any(word in text_lower for word in ['community', 'discord', 'forum']):
            return 'users'
        elif any(word in text_lower for word in ['documentation', 'docs', 'guide']):
            return 'book'
        else:
            return 'help-circle'
    
    def _clean_help_section_text(self, text: str) -> str:
        """Clean up help section text following technical writing rules."""
        # Remove excessive whitespace and improve formatting
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def convert_code_blocks(self, content: str) -> str:
        """Ensure code blocks are properly formatted for Mintlify."""
        # Already handled, but ensure proper spacing
        return content
    
    def validate_mdx(self, content: str) -> List[str]:
        """Validate MDX output for common issues."""
        errors = []
        
        # Check for unclosed tags
        tag_pattern = r'<(\w+)(?:\s+[^>]*)?>|</(\w+)>'
        tags_stack = []
        
        for match in re.finditer(tag_pattern, content):
            if match.group(2):  # Closing tag
                closing_tag = match.group(2)
                if not tags_stack or tags_stack[-1] != closing_tag:
                    errors.append(f"Unclosed or mismatched tag: </{closing_tag}>")
                else:
                    tags_stack.pop()
            else:  # Opening tag
                opening_tag = match.group(1)
                # Skip self-closing tags
                if not re.search(r'/>\s*$', match.group(0)):
                    tags_stack.append(opening_tag)
        
        if tags_stack:
            errors.append(f"Unclosed tags: {', '.join(tags_stack)}")
        
        # Check for JSX in code blocks
        code_blocks = re.findall(r'```[\w]*\n(.*?)```', content, re.DOTALL)
        for block in code_blocks:
            if re.search(r'<[A-Z]\w+', block):
                errors.append("Warning: JSX-like syntax found in code block")
        
        return errors
    
    def create_frontmatter(self, title: str, description: str = "", 
                          icon: str = "", mode: str = "") -> str:
        """Create Mintlify frontmatter."""
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
        """Remove the first H1 heading since it's in frontmatter."""
        return re.sub(r'^#\s+.+\n+', '', content, count=1)
    
    def convert(self, mdx_content: str, source_file: Path = None, **kwargs) -> str:
        """Main conversion method."""
        title = self.extract_title(mdx_content)
        
        # Use AI description if enabled and no description found
        if kwargs.get('use_ai_description'):
            description = self.generate_ai_description(mdx_content)
        else:
            description = self.extract_description(mdx_content)
        
        result = self.create_frontmatter(
            title, 
            description, 
            icon=kwargs.get('icon', ''),
            mode=kwargs.get('mode', '')
        )
        result += '\n\n'
        
        content = self.remove_original_title(mdx_content)
        
        # Apply conversions in order
        content = self.convert_banner(content)
        content = self.convert_api_links(content)
        content = self.convert_relative_links(content, source_file)
        content = self.handle_images(content, source_file)
        content = self.convert_lists_with_bold_headers(content)
        content = self.convert_tabs(content)
        content = self.convert_numbered_steps(content)
        content = self.convert_accordions(content)
        content = self.convert_callouts(content)
        content = self.convert_help_sections(content)
        content = self.convert_code_blocks(content)
        
        result += content
        
        # Validate if requested
        if kwargs.get('validate'):
            self.validation_errors = self.validate_mdx(result)
        
        return result


def process_file(input_path: Path, output_path: Path = None, 
                converter: MintlifyConverter = None, **kwargs):
    """Process a single MDX file."""
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


def process_directory(input_dir: Path, output_dir: Path, **kwargs):
    """Process all MDX files in a directory."""
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


def generate_enhanced_mint_json(file_metadata: Dict, output_path: Path, **kwargs):
    """Generate enhanced mint.json with nested groups and proper structure."""
    # Group files by directory
    groups = {}
    
    for file_path, meta in sorted(file_metadata.items()):
        group_name = meta['group']
        
        if group_name not in groups:
            groups[group_name] = []
        
        groups[group_name].append({
            'title': meta['title'],
            'path': meta['path']
        })
    
    # Sort pages within groups if requested
    if kwargs.get('sort_pages'):
        for group in groups.values():
            group.sort(key=lambda x: x['title'])
    
    # Build navigation structure
    navigation = []
    
    # Sort groups
    sorted_groups = sorted(groups.items(), key=lambda x: (x[0] != 'Documentation', x[0]))
    
    for group_name, pages in sorted_groups:
        # Use proper group titles
        group_title = group_name.replace('-', ' ').replace('_', ' ').title()
        
        navigation.append({
            'group': group_title,
            'pages': [page['path'] for page in pages]
        })
    
    mint_config = {
        'name': kwargs.get('project_name', 'Documentation'),
        'logo': {
            'dark': '/logo/dark.svg',
            'light': '/logo/light.svg'
        },
        'favicon': '/favicon.svg',
        'colors': {
            'primary': kwargs.get('primary_color', '#0D9373'),
            'light': kwargs.get('light_color', '#07C983'),
            'dark': kwargs.get('dark_color', '#0D9373'),
            'anchors': {
                'from': kwargs.get('primary_color', '#0D9373'),
                'to': kwargs.get('light_color', '#07C983')
            }
        },
        'topbarLinks': [
            {
                'name': 'Support',
                'url': kwargs.get('support_url', 'mailto:support@example.com')
            }
        ],
        'topbarCtaButton': {
            'name': 'Dashboard',
            'url': kwargs.get('dashboard_url', 'https://dashboard.example.com')
        },
        'navigation': navigation,
        'footerSocials': {
            'twitter': kwargs.get('twitter', 'https://twitter.com/example'),
            'github': kwargs.get('github', 'https://github.com/example'),
            'linkedin': kwargs.get('linkedin', 'https://www.linkedin.com/company/example')
        }
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(mint_config, f, indent=2)
    
    print(f"✓ Generated enhanced mint.json at {output_path}")


def main():
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
    
    parser.add_argument('input', type=str, help='Input MDX file or directory')
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
    
    input_path = Path(args.input)
    
    if not input_path.exists():
        print(f"Error: {input_path} does not exist", file=sys.stderr)
        sys.exit(1)
    
    kwargs = vars(args)
    
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