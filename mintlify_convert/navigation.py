#!/usr/bin/env python3
"""
Navigation and mint.json generation for Mintlify Convert.
"""

import json
from pathlib import Path
from typing import Dict


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


def create_basic_mint_json(output_path: Path, project_name: str = "Documentation"):
    """Create a basic mint.json file for simple setups."""
    basic_config = {
        'name': project_name,
        'logo': {
            'dark': '/logo/dark.svg',
            'light': '/logo/light.svg'
        },
        'favicon': '/favicon.svg',
        'colors': {
            'primary': '#0D9373',
            'light': '#07C983',
            'dark': '#0D9373'
        },
        'navigation': [
            {
                'group': 'Getting Started',
                'pages': ['getting-started']
            }
        ]
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(basic_config, f, indent=2)
    
    print(f"✓ Generated basic mint.json at {output_path}")


def validate_mint_json(mint_json_path: Path) -> bool:
    """Validate mint.json structure."""
    try:
        with open(mint_json_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        required_fields = ['name', 'navigation']
        for field in required_fields:
            if field not in config:
                print(f"Error: Missing required field '{field}' in mint.json")
                return False
        
        # Validate navigation structure
        if not isinstance(config['navigation'], list):
            print("Error: 'navigation' must be a list")
            return False
        
        for item in config['navigation']:
            if not isinstance(item, dict) or 'group' not in item or 'pages' not in item:
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
