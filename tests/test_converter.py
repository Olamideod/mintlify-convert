"""
Unit tests for the MintlifyConverter class.
"""

import pytest
from pathlib import Path
from mintlify_convert.converter import MintlifyConverter


class TestMintlifyConverter:
    """Test cases for MintlifyConverter."""
    
    @pytest.fixture
    def converter(self):
        """Create a converter instance for testing."""
        return MintlifyConverter()
    
    def test_extract_title(self, converter):
        """Test title extraction from content."""
        content = "# Getting Started\n\nThis is content"
        assert converter.extract_title(content) == "Getting Started"
        
        content_no_title = "No title here"
        assert converter.extract_title(content_no_title) == "Untitled"
    
    def test_extract_description(self, converter):
        """Test description extraction from content."""
        content = "# Title\n\nThis is the description paragraph."
        desc = converter.extract_description(content)
        assert "description paragraph" in desc
        
        content_no_desc = "# Title"
        desc = converter.extract_description(content_no_desc)
        assert desc == ""
    
    def test_convert_callouts(self, converter):
        """Test callout conversion."""
        content = "> **Warning:** This is important"
        result = converter.convert_callouts(content)
        assert '<Callout type="warning">' in result
        assert '</Callout>' in result
        
        content = "> **Tip:** This is helpful"
        result = converter.convert_callouts(content)
        assert '<Callout type="tip">' in result
    
    def test_convert_steps(self, converter):
        """Test steps conversion."""
        content = '''1. First step
2. Second step
3. Third step'''
        result = converter.convert_numbered_steps(content)
        assert '<Steps>' in result
        assert '<Step title="Step 1">' in result
        assert '</Steps>' in result
    
    def test_convert_api_links(self, converter):
        """Test API link conversion."""
        content = "[Get Services](/api/#operation/getServices-v1)"
        result = converter.convert_api_links(content)
        assert "/api-reference/getServices-v1" in result
    
    def test_convert_tabs(self, converter):
        """Test tabs conversion."""
        content = '''JavaScript:
const x = 1;

Python:
x = 1'''
        result = converter.convert_tabs(content)
        assert '<Tabs>' in result or 'JavaScript:' in result
    
    def test_convert_help_sections(self, converter):
        """Test help sections conversion."""
        content = "Need help?\n\nContact support@example.com"
        result = converter.convert_help_sections(content)
        assert '<Card title="Need help?"' in result
    
    def test_validate_mdx_unclosed_tags(self, converter):
        """Test MDX validation with unclosed tags."""
        content = "<Note>This is unclosed"
        errors = converter.validate_mdx(content)
        assert len(errors) > 0
        assert "Unclosed" in errors[0]
    
    def test_validate_mdx_clean(self, converter):
        """Test MDX validation with clean content."""
        content = "<Note>This is closed</Note>"
        errors = converter.validate_mdx(content)
        assert len(errors) == 0
    
    def test_full_conversion(self, converter):
        """Test full conversion process."""
        content = '''# API Documentation

This API helps you build amazing things.

## Getting Started

1. Sign up for an account
2. Get your API key
3. Make your first request

> **Note:** Keep your API key secure.

Need help?

Contact us at support@example.com
'''
        result = converter.convert(content)
        
        # Check frontmatter
        assert 'title: "API Documentation"' in result
        assert 'description:' in result
        
        # Check components
        assert '<Steps>' in result
        assert '<Callout' in result
        assert '<Card' in result


class TestImageHandling:
    """Test cases for image handling."""
    
    def test_handle_local_images(self, tmp_path):
        """Test local image handling."""
        # Create test structure
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        # Create test image
        img_path = input_dir / "test.png"
        img_path.write_bytes(b"fake image data")
        
        # Create MDX file
        mdx_content = "![Test](test.png)"
        mdx_file = input_dir / "doc.mdx"
        mdx_file.write_text(mdx_content)
        
        converter = MintlifyConverter(output_dir, download_assets=True)
        result = converter.handle_images(mdx_content, source_file=mdx_file)
        
        assert "/images/test.png" in result


class TestFrontmatterGeneration:
    """Test cases for frontmatter generation."""
    
    def test_create_frontmatter_basic(self):
        """Test basic frontmatter creation."""
        converter = MintlifyConverter()
        fm = converter.create_frontmatter("Test Title", "Test description")
        
        assert 'title: "Test Title"' in fm
        assert 'description: "Test description"' in fm
        assert fm.startswith('---')
        assert fm.endswith('---')
    
    def test_create_frontmatter_with_icon(self):
        """Test frontmatter creation with icon."""
        converter = MintlifyConverter()
        fm = converter.create_frontmatter("Test Title", icon="shield", mode="wide")
        
        assert 'icon: "shield"' in fm
        assert 'mode: "wide"' in fm
    
    def test_remove_original_title(self):
        """Test removal of original title."""
        converter = MintlifyConverter()
        content = "# Original Title\n\nContent here"
        result = converter.remove_original_title(content)
        
        assert "# Original Title" not in result
        assert "Content here" in result