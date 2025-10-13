"""
Tests for navigation and mint.json generation.
"""

import pytest
import json
from pathlib import Path
from mintlify_convert.navigation import (
    generate_enhanced_mint_json,
    create_basic_mint_json,
    validate_mint_json
)


class TestMintJsonGeneration:
    """Test cases for mint.json generation."""
    
    def test_generate_enhanced_mint_json(self, tmp_path):
        """Test enhanced mint.json generation."""
        file_metadata = {
            "getting-started/intro": {
                "title": "Introduction",
                "path": "getting-started/intro",
                "group": "getting-started"
            },
            "api/auth": {
                "title": "Authentication",
                "path": "api/auth",
                "group": "api"
            },
            "guides/best-practices": {
                "title": "Best Practices",
                "path": "guides/best-practices",
                "group": "guides"
            }
        }
        
        output_file = tmp_path / "mint.json"
        generate_enhanced_mint_json(
            file_metadata, 
            output_file, 
            project_name="Test API",
            primary_color="#FF6B6B",
            support_url="https://support.test.com"
        )
        
        assert output_file.exists()
        
        with open(output_file) as f:
            config = json.load(f)
        
        # Check basic structure
        assert config['name'] == "Test API"
        assert config['colors']['primary'] == "#FF6B6B"
        assert config['topbarLinks'][0]['url'] == "https://support.test.com"
        
        # Check navigation structure
        assert len(config['navigation']) == 3
        assert config['navigation'][0]['group'] == "Getting Started"
        assert "getting-started/intro" in config['navigation'][0]['pages']
    
    def test_generate_mint_json_with_sorting(self, tmp_path):
        """Test mint.json generation with page sorting."""
        file_metadata = {
            "docs/zeebra": {"title": "Zeebra", "path": "docs/zeebra", "group": "docs"},
            "docs/apple": {"title": "Apple", "path": "docs/apple", "group": "docs"},
            "docs/banana": {"title": "Banana", "path": "docs/banana", "group": "docs"}
        }
        
        output_file = tmp_path / "mint.json"
        generate_enhanced_mint_json(file_metadata, output_file, sort_pages=True)
        
        with open(output_file) as f:
            config = json.load(f)
        
        # Check that pages are sorted alphabetically
        pages = config['navigation'][0]['pages']
        assert pages == ["docs/apple", "docs/banana", "docs/zeebra"]
    
    def test_create_basic_mint_json(self, tmp_path):
        """Test basic mint.json creation."""
        output_file = tmp_path / "mint.json"
        create_basic_mint_json(output_file, "Basic Project")
        
        assert output_file.exists()
        
        with open(output_file) as f:
            config = json.load(f)
        
        assert config['name'] == "Basic Project"
        assert config['navigation'][0]['group'] == "Getting Started"
        assert config['navigation'][0]['pages'] == ["getting-started"]


class TestMintJsonValidation:
    """Test cases for mint.json validation."""
    
    def test_validate_valid_mint_json(self, tmp_path):
        """Test validation of valid mint.json."""
        mint_json = tmp_path / "mint.json"
        mint_json.write_text('''{
            "name": "Test Project",
            "navigation": [
                {
                    "group": "Getting Started",
                    "pages": ["intro", "setup"]
                }
            ]
        }''')
        
        assert validate_mint_json(mint_json) is True
    
    def test_validate_invalid_mint_json_missing_name(self, tmp_path):
        """Test validation of mint.json missing required name field."""
        mint_json = tmp_path / "mint.json"
        mint_json.write_text('''{
            "navigation": [
                {
                    "group": "Getting Started",
                    "pages": ["intro"]
                }
            ]
        }''')
        
        assert validate_mint_json(mint_json) is False
    
    def test_validate_invalid_mint_json_missing_navigation(self, tmp_path):
        """Test validation of mint.json missing navigation."""
        mint_json = tmp_path / "mint.json"
        mint_json.write_text('''{
            "name": "Test Project"
        }''')
        
        assert validate_mint_json(mint_json) is False
    
    def test_validate_invalid_mint_json_bad_navigation(self, tmp_path):
        """Test validation of mint.json with invalid navigation structure."""
        mint_json = tmp_path / "mint.json"
        mint_json.write_text('''{
            "name": "Test Project",
            "navigation": "invalid"
        }''')
        
        assert validate_mint_json(mint_json) is False
    
    def test_validate_invalid_json_syntax(self, tmp_path):
        """Test validation of invalid JSON syntax."""
        mint_json = tmp_path / "mint.json"
        mint_json.write_text('{"name": "Test Project", "navigation": [')  # Invalid JSON
        
        assert validate_mint_json(mint_json) is False
    
    def test_validate_nonexistent_file(self, tmp_path):
        """Test validation of non-existent file."""
        mint_json = tmp_path / "nonexistent.json"
        
        assert validate_mint_json(mint_json) is False


class TestNavigationGrouping:
    """Test cases for navigation grouping logic."""
    
    def test_group_title_formatting(self, tmp_path):
        """Test that group titles are properly formatted."""
        file_metadata = {
            "api-reference/auth": {"title": "Auth", "path": "api-reference/auth", "group": "api-reference"},
            "getting-started/intro": {"title": "Intro", "path": "getting-started/intro", "group": "getting-started"}
        }
        
        output_file = tmp_path / "mint.json"
        generate_enhanced_mint_json(file_metadata, output_file)
        
        with open(output_file) as f:
            config = json.load(f)
        
        # Check that group names are properly formatted
        groups = [nav['group'] for nav in config['navigation']]
        assert "Api Reference" in groups
        assert "Getting Started" in groups
    
    def test_documentation_group_priority(self, tmp_path):
        """Test that Documentation group comes first."""
        file_metadata = {
            "advanced/features": {"title": "Features", "path": "advanced/features", "group": "advanced"},
            "intro": {"title": "Intro", "path": "intro", "group": "Documentation"}
        }
        
        output_file = tmp_path / "mint.json"
        generate_enhanced_mint_json(file_metadata, output_file)
        
        with open(output_file) as f:
            config = json.load(f)
        
        # Documentation group should come first
        assert config['navigation'][0]['group'] == "Documentation"
