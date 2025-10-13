# Mintlify Convert

[![PyPI version](https://badge.fury.io/py/mintlify-convert.svg)](https://badge.fury.io/py/mintlify-convert)
[![Python Support](https://img.shields.io/pypi/pyversions/mintlify-convert.svg)](https://pypi.org/project/mintlify-convert/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/yourusername/mintlify-convert/workflows/Tests/badge.svg)](https://github.com/yourusername/mintlify-convert/actions)

Convert MDX documentation to Mintlify format with enhanced features for seamless migration.

## ✨ Features

### 🎯 Core Conversions
- ✅ Frontmatter generation (title, description, icon, mode)
- ✅ Callouts/Admonitions → Proper Mintlify components (`<Warning>`, `<Tip>`, `<Note>`, `<Info>`, `<Check>`)
- ✅ Numbered lists → `<Steps>` component with intelligent title extraction
- ✅ Help sections → `<Card>` components with contextual icons
- ✅ API links → Mintlify API reference format
- ✅ Code blocks with proper formatting

### 🧩 Advanced Components (Enhanced with Technical Writing Rules)
- ✅ `<Accordion>` blocks (smart detection from H3 sections)
- ✅ `<Tabs>` and `<Tab>` (enhanced language detection and proper display names)
- ✅ `<Banner>` for important notices
- ✅ `<Frame>` wrapped images for better presentation
- ✅ Intelligent component selection based on content context

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

## 🚀 Quick Start

### Installation

```bash
# From PyPI (when published)
pip install mintlify-convert

# From source
git clone https://github.com/yourusername/mintlify-convert.git
cd mintlify-convert
pip install -e .
```

### Basic Usage

```bash
# Convert a single file
mintlify-convert input.mdx -o output.mdx

# Convert an entire directory
mintlify-convert docs/ -o mintlify-docs/

# With all features
mintlify-convert docs/ -o mintlify-docs/ \
  --generate-mint-json \
  --download-assets \
  --validate \
  --sort-pages
```

## 📖 Documentation

- **[Getting Started](docs/getting-started.md)** - Quick start guide
- **[API Reference](docs/api-reference.md)** - Complete CLI and programmatic API
- **[Component Mapping](docs/component-mapping.md)** - How patterns are converted
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions

## 🎯 Component Conversions

### Callouts (Enhanced)
**Input:**
```markdown
> **Warning:** This is a critical note.
> Please read carefully.
```

**Output:**
```mdx
<Warning>
**Warning:** This is a critical note.
Please read carefully.
</Warning>
```

### Steps (Enhanced with Smart Titles)
**Input:**
```markdown
1. Install dependencies using npm
2. Configure your environment variables
3. Start the development server
```

**Output:**
```mdx
<Steps>
  <Step title="Install dependencies using npm">
  Install dependencies using npm
  </Step>
  <Step title="Configure your environment variables">
  Configure your environment variables
  </Step>
  <Step title="Start the development server">
  Start the development server
  </Step>
</Steps>
```

### Tabs (Enhanced Language Support)
**Input:**
```markdown
JavaScript:
const api = require('api');

Python:
import api

Node.js:
const api = require('api');
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
  <Tab title="Node.js">
```javascript
const api = require('api');
```
  </Tab>
</Tabs>
```

##  Development

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

### Run Mintlify Convert (Enhanced with Technical Writing Rules)
```bash
# Convert all MDX files in docs/ to mintlify format with enhanced components
python -m mintlify_convert.cli docs/ -o mintlify-docs/ --generate-mint-json

# Or use the standalone script (legacy)
python mintlify_convert.py docs/ -o mintlify-docs/ --generate-mint-json
```

### Stand Alone Code
```bash
# Using the CLI module
python -m mintlify_convert.cli doc.mdx -o output.mdx

# Or using the standalone script
python mintlify_convert.py doc.mdx -o output.mdx
```

### One-Command URL Scrape → Convert (New)
```bash
# Scrape a live URL, download images, save MDX, convert to Mintlify, and generate mint.json
python -m mintlify_convert.cli --url https://example.com/docs/quickstart -o mintlify-docs/ --generate-mint-json --download-assets --validate
```

### Install & Run
```bash
# 1) Install
pip install -e ".[dev]"

# 2) URL → Mintlify (single step)
python -m mintlify_convert.cli --url https://example.com/docs/quickstart -o mintlify-docs/ --generate-mint-json

# 3) Directory → Mintlify
python -m mintlify_convert.cli docs/ -o mintlify-docs/ --generate-mint-json
```

### Enhanced Features with Technical Writing Rules
The converter now follows Mintlify's technical writing best practices as defined in [agent.md](agent.md):

- **Proper Component Usage**: Uses `<Warning>`, `<Tip>`, `<Note>`, `<Info>`, `<Check>` instead of generic callouts
- **Enhanced Steps**: Extracts meaningful titles from step content
- **Smart Accordions**: Automatically detects accordion-worthy content
- **Frame-wrapped Images**: All images are wrapped in `<Frame>` components for better presentation
- **Improved Tabs**: Better language detection and proper display names
- **Contextual Help Cards**: Smart icon selection based on content type

### Code Formatting
```bash
black mintlify_convert/
flake8 mintlify_convert/
mypy mintlify_convert/
```

##  Project Structure

```
mintlify-convert/
├── mintlify_convert/           # Main package
│   ├── __init__.py            # Package initialization
│   ├── cli.py                 # Command-line interface
│   ├── converter.py           # Core conversion logic
│   ├── navigation.py          # mint.json generation
│   └── utils.py               # Helper utilities
│
├── tests/                      # Test suite
│   ├── test_converter.py      # Unit tests for converter
│   ├── test_integration.py    # Integration tests
│   ├── test_navigation.py     # Navigation tests
│   └── fixtures/              # Test fixtures
│
├── examples/                   # Example conversions
│   ├── basic/                 # Basic examples
│   ├── advanced/              # Advanced examples
│   └── full-migration/        # Complete migration example
│
├── docs/                       # Package documentation
│   ├── getting-started.md
│   ├── api-reference.md
│   ├── component-mapping.md
│   └── troubleshooting.md
│
├── .github/
│   └── workflows/             # CI/CD workflows
│
├── pyproject.toml             # Modern Python project config
├── requirements.txt           # Dependencies
├── requirements-dev.txt       # Development dependencies
├── README.md                  # This file
├── LICENSE                    # MIT License
├── CHANGELOG.md              # Version history
├── agent.md                   # Mintlify technical writing rules
└── .gitignore                # Git ignore rules
```

## 🗺️ Roadmap

### Phase 3 (Future)
- [ ] AI-powered description generation
- [ ] Parallel processing for large docs
- [ ] Interactive migration wizard (TUI)
- [ ] Incremental conversion (only changed files)
- [ ] Custom component plugins
- [ ] Automatic image optimization
- [ ] Diff viewer for conversions
- [ ] VS Code extension
- [ ] Web-based converter UI
- [ ] Support for Docusaurus → Mintlify
- [ ] Support for GitBook → Mintlify
- [ ] Migration analytics and reporting

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

##  Support

-  **Email**: support@example.com
-  **Discord**: [Join our community](https://discord.gg/example)
-  **Issues**: [GitHub Issues](https://github.com/yourusername/mintlify-convert/issues)
-  **Docs**: [Full Documentation](https://docs.example.com)

## Acknowledgments

Built with ❤️ to help teams migrate to Mintlify faster.

*Star ⭐ this repo if it helped you!*