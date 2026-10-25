"""
Integration tests for mintlify-convert.
"""

from mintlify_convert.utils import process_directory, process_file
from mintlify_convert.navigation import generate_enhanced_mint_json


def test_full_directory_conversion(tmp_path):
    """Test converting an entire directory structure."""
    # Create test directory structure
    input_dir = tmp_path / "docs"
    input_dir.mkdir()

    (input_dir / "intro.mdx").write_text("# Introduction\n\nWelcome to our docs.")

    api_dir = input_dir / "api"
    api_dir.mkdir()
    (api_dir / "auth.mdx").write_text("# Authentication\n\nAPI auth guide.")

    output_dir = tmp_path / "output"

    # Run conversion
    file_metadata = process_directory(input_dir, output_dir)

    assert len(file_metadata) == 2
    assert (output_dir / "intro.mdx").exists()
    assert (output_dir / "api" / "auth.mdx").exists()


def test_single_file_conversion(tmp_path):
    """Test converting a single file."""
    input_file = tmp_path / "test.mdx"
    input_file.write_text("# Test Document\n\nThis is a test.")

    output_file = tmp_path / "converted.mdx"

    success, title = process_file(input_file, output_file)

    assert success
    assert title == "Test Document"
    assert output_file.exists()

    # Check that frontmatter was added
    content = output_file.read_text()
    assert 'title: "Test Document"' in content
    assert content.startswith("---")


def test_navigation_generation(tmp_path):
    """Test mint.json generation."""
    file_metadata = {
        "getting-started/intro": {
            "title": "Introduction",
            "path": "getting-started/intro",
            "group": "getting-started",
        },
        "api/auth": {"title": "Authentication", "path": "api/auth", "group": "api"},
    }

    output_file = tmp_path / "mint.json"
    generate_enhanced_mint_json(file_metadata, output_file, project_name="Test Project")

    assert output_file.exists()

    # Check JSON structure
    import json

    with open(output_file) as f:
        config = json.load(f)

    assert config["name"] == "Test Project"
    assert "navigation" in config
    assert len(config["navigation"]) == 2


def test_conversion_with_assets(tmp_path):
    """Test conversion with asset copying."""
    input_dir = tmp_path / "docs"
    input_dir.mkdir()
    output_dir = tmp_path / "output"

    # Create test files
    (input_dir / "page.mdx").write_text("# Page\n\n![Image](test.png)")
    (input_dir / "test.png").write_bytes(b"fake image data")

    # Run conversion with asset copying
    file_metadata = process_directory(input_dir, output_dir, download_assets=True)

    assert len(file_metadata) == 1
    assert (output_dir / "images" / "test.png").exists()

    # Check that image path was updated
    content = (output_dir / "page.mdx").read_text()
    assert "/images/test.png" in content


def test_conversion_with_validation(tmp_path):
    """Test conversion with MDX validation."""
    input_dir = tmp_path / "docs"
    input_dir.mkdir()
    output_dir = tmp_path / "output"

    # Create test file with potential issues
    (input_dir / "page.mdx").write_text("# Page\n\n<Unclosed>")

    # Run conversion with validation
    file_metadata = process_directory(input_dir, output_dir, validate=True)

    assert len(file_metadata) == 1
    assert (output_dir / "page.mdx").exists()


def test_component_conversions(tmp_path):
    """Test various component conversions."""
    input_file = tmp_path / "test.mdx"
    test_content = """# Component Test

> **Warning:** This is important

1. First step
2. Second step

Need help?

Contact support@example.com

### Advanced Section
This is advanced content that should become an accordion.
"""

    input_file.write_text(test_content)
    output_file = tmp_path / "converted.mdx"

    success, title = process_file(input_file, output_file)

    assert success
    content = output_file.read_text()

    # Check various conversions
    assert "<Warning>" in content
    assert "<Callout" not in content
    assert "<Steps>" in content
    assert "<Card" in content
    assert "<Accordion" in content


def test_error_handling(tmp_path):
    """Test error handling in conversion."""
    # Test with non-existent file
    input_file = tmp_path / "nonexistent.mdx"
    output_file = tmp_path / "output.mdx"

    success, title = process_file(input_file, output_file)

    assert not success
    assert title is None
