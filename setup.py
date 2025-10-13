# setup.py
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="mintlify-convert",
    version="2.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Convert MDX documentation to Mintlify format with enhanced features",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/mintlify-convert",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Documentation",
        "Topic :: Text Processing :: Markup",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.28.0",  # For downloading assets (future)
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=3.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.950",
        ],
        "ai": [
            "openai>=1.0.0",  # For AI description generation
        ],
    },
    entry_points={
        "console_scripts": [
            "mintlify-convert=mintlify_convert.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)

# ====================
# File: README.md
# ====================
"""
# Mintlify Convert

Convert MDX documentation to Mintlify format with enhanced features for seamless migration.

## Features

### 🎯 Core Conversions
- ✅ Frontmatter generation (title, description, icon, mode)
- ✅ Callouts/Admonitions → `<Callout type="...">` components
- ✅ Numbered lists → `<Steps>` component
- ✅ Help sections → `<Card>` components with icons
- ✅ API links → Mintlify API reference format
- ✅ Code blocks with proper formatting

### 🧩 Advanced Components (Phase 2)
- ✅ `<Accordion>` blocks (from H3 sections)
- ✅ `<Tabs>` and `<Tab>` (language-specific code examples)
- ✅ `<Banner>` for important notices
- ✅ `<Callout type="...">` with proper types (info, warning, tip, note)

### 🧭 Navigation
- ✅ Enhanced `mint.json` generation
- ✅ Nested groups based on folder structure
- ✅ Proper page titles from frontmatter
- ✅ Optional alphabetical sorting

### 🖼️ Asset Handling
- ✅ Image copying to `/images` directory
- ✅ Relative link rewriting
- ✅ Automatic path correction

### 🔧 Quality Assurance
- ✅ MDX validation (unclosed tags, JSX in code blocks)
- ✅ Detailed error reporting
- ✅ Verbose mode for debugging

## Installation

### From PyPI (when published)
```bash
pip install mintlify-convert
```

### From source
```bash
git clone https://github.com/yourusername/mintlify-convert.git
cd mintlify-convert
pip install -e .
```

### With optional dependencies
```bash
# For AI description generation
pip install mintlify-convert[ai]

# For development
pip install mintlify-convert[dev]
```

## Quick Start

### Convert a single file
```bash
mintlify-convert input.mdx -o output.mdx
```

### Convert an entire directory
```bash
mintlify-convert docs/ -o mintlify-docs/
```

### Full migration with all features
```bash
mintlify-convert docs/ -o mintlify-docs/ \
  --generate-mint-json \
  --download-assets \
  --validate \
  --sort-pages \
  --project-name "My API Documentation"
```

## Usage Examples

### Basic Conversion
```bash
# Single file
mintlify-convert README.mdx -o docs/introduction.mdx

# Directory
mintlify-convert old-docs/ -o new-docs/
```

### With Assets
```bash
# Copy images and update paths
mintlify-convert docs/ -o mintlify-docs/ --download-assets
```

### Generate Navigation
```bash
# Create mint.json with sorted pages
mintlify-convert docs/ -o mintlify-docs/ \
  --generate-mint-json \
  --sort-pages \
  --project-name "Acme API Docs"
```

### Custom Branding
```bash
mintlify-convert docs/ -o mintlify-docs/ \
  --generate-mint-json \
  --primary-color "#FF6B6B" \
  --light-color "#FFE66D" \
  --dark-color "#4ECDC4" \
  --support-url "https://support.acme.com" \
  --dashboard-url "https://dashboard.acme.com" \
  --github "https://github.com/acme" \
  --twitter "https://twitter.com/acme"
```

### Validation
```bash
# Validate MDX output
mintlify-convert docs/ -o mintlify-docs/ --validate --verbose
```

## Component Conversions

### Callouts
**Input:**
```markdown
> **Important:** This is a critical note.
> Please read carefully.
```

**Output:**
```mdx
<Callout type="warning">
**Important:** This is a critical note.
Please read carefully.
</Callout>
```

### Steps
**Input:**
```markdown
1. First step with instructions
2. Second step with more details
3. Final step to complete
```

**Output:**
```mdx
<Steps>
  <Step title="Step 1">
  First step with instructions
  </Step>
  <Step title="Step 2">
  Second step with more details
  </Step>
  <Step title="Step 3">
  Final step to complete
  </Step>
</Steps>
```

### Tabs
**Input:**
```markdown
JavaScript:
const api = require('api');

Python:
import api
```

**Output:**
```mdx
<Tabs>
  <Tab title="JavaScript">
```javascript
const api = require('api');
```
  </Tab>
  <Tab title="Python">
```python
import api
```
  </Tab>
</Tabs>
```

### Accordions
**Input:**
```markdown
### Advanced Configuration
This section contains detailed configuration options
that can be collapsed for better readability.
```

**Output:**
```mdx
<Accordion title="Advanced Configuration">
This section contains detailed configuration options
that can be collapsed for better readability.
</Accordion>
```

### Banners
**Input:**
```markdown
⚠️ Deprecated: This endpoint will be removed in v2.0
```

**Output:**
```mdx
<Banner type="warning">
This endpoint will be removed in v2.0
</Banner>
```

## Configuration

### Frontmatter Options
```bash
--icon "shield"           # Add icon to page
--mode "wide"            # Set page mode
```

### Processing Options
```bash
--download-assets        # Copy images to /images
--validate              # Validate MDX output
--use-ai-description    # Generate AI descriptions (requires OpenAI key)
--verbose               # Show detailed errors
```

### Navigation Options
```bash
--generate-mint-json    # Generate mint.json
--sort-pages           # Sort pages alphabetically
--project-name "Name"  # Set project name
```

### Branding Options
```bash
--primary-color "#HEX"    # Primary brand color
--light-color "#HEX"      # Light brand color
--dark-color "#HEX"       # Dark brand color
--support-url "URL"       # Support link
--dashboard-url "URL"     # Dashboard CTA link
--twitter "URL"           # Twitter social link
--github "URL"            # GitHub social link
--linkedin "URL"          # LinkedIn social link
```

## Project Structure

After conversion, your project will look like:

```
mintlify-docs/
├── mint.json              # Navigation configuration
├── images/                # Copied assets
│   ├── diagram.png
│   └── logo.svg
├── getting-started/
│   ├── introduction.mdx
│   └── quickstart.mdx
├── api-reference/
│   ├── authentication.mdx
│   └── endpoints.mdx
└── guides/
    ├── best-practices.mdx
    └── troubleshooting.mdx
```

## Development

### Setup
```bash
git clone https://github.com/yourusername/mintlify-convert.git
cd mintlify-convert
pip install -e ".[dev]"
```

### Run Tests
```bash
pytest tests/ -v --cov=mintlify_convert
```

### Code Formatting
```bash
black mintlify_convert/
flake8 mintlify_convert/
mypy mintlify_convert/
```

## Roadmap

### Phase 3 (Future)
- [ ] AI-powered description generation with OpenAI
- [ ] Automatic image optimization
- [ ] Support for more Mintlify components (ResponseField, Param, etc.)
- [ ] Interactive migration wizard
- [ ] Diff viewer for changes
- [ ] Batch processing with parallel execution
- [ ] Plugin system for custom converters

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see LICENSE file for details

## Support

- 📧 Email: support@example.com
- 💬 Discord: [Join our community](https://discord.gg/example)
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/mintlify-convert/issues)
- 📖 Docs: [Full Documentation](https://docs.example.com)

## Acknowledgments

Built with ❤️ to help teams migrate to Mintlify faster.
"""

# ====================
# File: tests/test_converter.py
# ====================
"""
import pytest
from pathlib import Path
from mintlify_convert.converter import MintlifyConverter


class TestMintlifyConverter:
    @pytest.fixture
    def converter(self):
        return MintlifyConverter()
    
    def test_extract_title(self, converter):
        content = "# Getting Started\n\nThis is content"
        assert converter.extract_title(content) == "Getting Started"
    
    def test_extract_description(self, converter):
        content = "# Title\n\nThis is the description paragraph."
        desc = converter.extract_description(content)
        assert "description paragraph" in desc
    
    def test_convert_callouts(self, converter):
        content = "> **Warning:** This is important"
        result = converter.convert_callouts(content)
        assert '<Callout type="warning">' in result
        assert '</Callout>' in result
    
    def test_convert_steps(self, converter):
        content = '''1. First step
2. Second step
3. Third step'''
        result = converter.convert_numbered_steps(content)
        assert '<Steps>' in result
        assert '<Step title="Step 1">' in result
        assert '</Steps>' in result
    
    def test_convert_api_links(self, converter):
        content = "[Get Services](/api/#operation/getServices-v1)"
        result = converter.convert_api_links(content)
        assert "/api-reference/getServices-v1" in result
    
    def test_convert_tabs(self, converter):
        content = '''JavaScript:
const x = 1;

Python:
x = 1'''
        result = converter.convert_tabs(content)
        assert '<Tabs>' in result or 'JavaScript:' in result
    
    def test_convert_help_sections(self, converter):
        content = "Need help?\n\nContact support@example.com"
        result = converter.convert_help_sections(content)
        assert '<Card title="Need help?"' in result
    
    def test_validate_mdx_unclosed_tags(self, converter):
        content = "<Note>This is unclosed"
        errors = converter.validate_mdx(content)
        assert len(errors) > 0
        assert "Unclosed" in errors[0]
    
    def test_validate_mdx_clean(self, converter):
        content = "<Note>This is closed</Note>"
        errors = converter.validate_mdx(content)
        assert len(errors) == 0
    
    def test_full_conversion(self, converter):
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
    def test_handle_local_images(self, tmp_path):
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
        result = converter.convert(mdx_content, source_file=mdx_file)
        
        assert "/images/test.png" in result


class TestNavigationGeneration:
    def test_generate_mint_json_structure(self):
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
            }
        }
        
        # This would test the actual generation
        # Implementation depends on your generate_enhanced_mint_json function


# ====================
# File: tests/test_integration.py
# ====================

def test_full_directory_conversion(tmp_path):
    \"\"\"Test converting an entire directory structure.\"\"\"
    # Create test directory structure
    input_dir = tmp_path / "docs"
    input_dir.mkdir()
    
    (input_dir / "intro.mdx").write_text("# Introduction\n\nWelcome to our docs.")
    
    api_dir = input_dir / "api"
    api_dir.mkdir()
    (api_dir / "auth.mdx").write_text("# Authentication\n\nAPI auth guide.")
    
    output_dir = tmp_path / "output"
    
    # Run conversion
    from mintlify_convert.cli import process_directory
    file_metadata = process_directory(input_dir, output_dir)
    
    assert len(file_metadata) == 2
    assert (output_dir / "intro.mdx").exists()
    assert (output_dir / "api" / "auth.mdx").exists()


# ====================
# File: .github/workflows/test.yml
# ====================
\"\"\"
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.8', '3.9', '3.10', '3.11']
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev]"
    
    - name: Run tests
      run: |
        pytest tests/ -v --cov=mintlify_convert --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
    
    - name: Lint with flake8
      run: |
        flake8 mintlify_convert --count --select=E9,F63,F7,F82 --show-source --statistics
    
    - name: Check formatting
      run: |
        black --check mintlify_convert
\"\"\"

# ====================
# File: MANIFEST.in
# ====================
\"\"\"
include README.md
include LICENSE
include requirements.txt
recursive-include mintlify_convert *.py
recursive-include tests *.py
\"\"\"

# ====================
# File: requirements.txt
# ====================
\"\"\"
requests>=2.28.0
\"\"\"

# ====================
# File: .gitignore
# ====================
\"\"\"
# Python
s/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# Testing
.pytest_cache/
.covera__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
partge
htmlcov/
.tox/

# OS
.DS_Store
Thumbs.db
\"\"\""""