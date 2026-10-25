# Mintlify Convert

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Convert MDX documentation to Mintlify format with enhanced features for seamless migration.

## ✨ Features

### 🎯 Core Conversions
- ✅ Frontmatter generation (title, description, icon, mode)
- ✅ Callouts/Admonitions → Proper Mintlify components (`<Warning>`, `<Tip>`, `<Note>`, `<Info>`, `<Check>`)
- ✅ Numbered lists → one `<Steps>` per list, with plain-text titles taken from each step
- ✅ Help sections → `<Card>` components with contextual icons
- ✅ API links → Mintlify API reference format
- ✅ Code blocks with proper formatting

### 🧩 Advanced Components (Enhanced with Technical Writing Rules)
- ✅ `<Accordion>` for H3 sections whose titles match a keyword heuristic (troubleshooting, FAQ, advanced, common issues, known issues, error codes, walkthrough, step by step, breakdown)
- ✅ `<Tabs>` and `<Tab>` for language-labelled code blocks, with display names such as "JavaScript"
- ✅ `<Banner>` for paragraphs that start with "Deprecated:", "Important:", "Notice:" or "Alert:"
- ✅ `<Frame>` around images that are copied with `--download-assets`

### 🧭 Navigation
- ✅ `docs.json` generation (default), or legacy `mint.json` with `--legacy-mint-json`
- ✅ Nested groups based on folder structure ("Getting Started" first, then "Documentation", then A-Z)
- ✅ Proper page titles from frontmatter
- ✅ Optional alphabetical sorting

### 🖼️ Asset Handling
- ✅ Image copying to `/images` directory (only with `--download-assets`, only from inside the input directory)
- ✅ Relative link rewriting (links that resolve outside the input directory are left unchanged)
- ✅ Automatic path correction

### 🔧 Quality Assurance
- ✅ Input files over 1 MiB are rejected; symlinked inputs and `file:` images are skipped with a warning on stderr
- ✅ MDX validation (unclosed or mismatched tags; code blocks are ignored)
- ✅ Detailed error reporting
- ✅ Verbose mode for debugging

## 🚀 Quick Start

### Installation

Requires Python 3.10 or newer.

```bash
pip install mintlify-convert
```

Or from source:

```bash
git clone https://github.com/Olamideod/mintlify-convert.git
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
  --generate-config \
  --download-assets \
  --validate \
  --sort-pages
```

`--generate-config` writes `docs.json`. Add `--legacy-mint-json` to write `mint.json` instead. `--generate-mint-json` is a deprecated alias for both flags together.

Converting is idempotent: running the tool on its own output produces the same output. The output path must not be the same as, or inside, the input path.

## 📖 Documentation

- **[Getting Started](docs/getting-started.mdx)** - Quick start guide
- **[API Reference](docs/api-reference.mdx)** - Complete CLI and programmatic API
- **[Component Mapping](docs/component-mapping.mdx)** - How patterns are converted
- **[Troubleshooting](docs/troubleshooting.mdx)** - Common issues and solutions

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
```

**Output:**
````mdx
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
````

##  Development

### Setup
```bash
git clone https://github.com/Olamideod/mintlify-convert.git
cd mintlify-convert
pip install -e ".[dev]"
```

### Run Tests
```bash
pytest tests/ -v --cov=mintlify_convert
```

### Run Mintlify Convert
```bash
# Convert all MDX files in docs/ and write docs.json
python -m mintlify_convert.cli docs/ -o mintlify-docs/ --generate-config

# Convert a single file
python -m mintlify_convert.cli doc.mdx -o output.mdx
```

### Conversion behaviour
The converter follows the component guidance in [agent.md](agent.md):

- Callouts become `<Warning>`, `<Tip>`, `<Note>`, `<Info>` or `<Check>`
- Numbered lists become `<Steps>` with descriptive titles taken from each step
- Accordions, Banners and Frames follow the narrow rules listed under Features
- Callouts, banners and numbered lists that start with a code fence are left unconverted; banners and help cards only match at the start of a paragraph
- Three or more consecutive language-labelled blocks form one `<Tabs>` group
- Code fences are left untouched

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
│   ├── navigation.py          # docs.json / mint.json generation
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
│   ├── getting-started.mdx
│   ├── api-reference.mdx
│   ├── component-mapping.mdx
│   └── troubleshooting.mdx
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

### Future work
- [ ] AI-powered description generation (not implemented)
- [ ] Parallel processing for large docs (not implemented)
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

## Support

- Issues: [GitHub Issues](https://github.com/Olamideod/mintlify-convert/issues)

## 🙏 Acknowledgments

Built with ❤️ to help teams migrate to Mintlify faster.

*Star ⭐ this repo if it helped you!*