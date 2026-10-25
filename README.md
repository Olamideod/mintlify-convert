# Mintlify Convert

[![PyPI](https://img.shields.io/pypi/v/mintlify-convert)](https://pypi.org/project/mintlify-convert/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

You have a documentation site written in MDX, and you want it on Mintlify. Mintlify renders callouts, step lists, and tabbed code as components, and it reads navigation from a `docs.json` file. Moving the pages means rewriting each of those patterns by hand and writing the navigation file yourself. Mintlify Convert rewrites the patterns from the command line and generates `docs.json`. This README shows how to install it, what it converts, and where it stops.

## Install

The package needs Python 3.10 or newer. Install it from PyPI:

```bash
pip install mintlify-convert
```

To work from source, clone the repository and install it in editable mode:

```bash
git clone https://github.com/Olamideod/mintlify-convert.git
cd mintlify-convert
pip install -e .
```

## Convert your docs

Point the command at a file or a directory and set an output path. The tool prints one line for each converted file. With `--validate`, it also prints a warning for each file that has problems.

```bash
# Convert one file
mintlify-convert INPUT.mdx -o OUTPUT.mdx

# Convert a directory
mintlify-convert DOCS_DIR/ -o OUTPUT_DIR/

# Convert a directory, write docs.json, and check the output
mintlify-convert DOCS_DIR/ -o OUTPUT_DIR/ --generate-config --validate --sort-pages
```

The `--generate-config` option writes `docs.json` in the output directory, with navigation groups that follow your folder structure. If you need the older `mint.json`, then add `--legacy-mint-json`.

> [!NOTE]
> The output path can't match the input path or sit inside it. Running the tool on its own output produces the same output.

## What it converts

The table below lists each pattern the tool recognizes and the component it writes. The examples after the table show the page body only. The tool also writes frontmatter above it, with a title and, when the page has an opening paragraph, a description.

| Input | Output | Rule |
| --- | --- | --- |
| Blockquote | `<Warning>`, `<Note>`, `<Tip>`, `<Info>`, or `<Check>` | Uses a leading label such as `Warning:` or `Tip:`. Without a label, it looks for keywords and falls back to `<Info>`. |
| Numbered list | `<Steps>` with one `<Step>` for each item | The title is the first sentence or clause, up to about 80 characters. The body keeps the full text. |
| Two or more blocks that start with a language label, such as `Python:` | `<Tabs>` with one `<Tab>` for each block | Wraps each block in a code fence for that language. |
| `###` heading with a keyword in its title | `<Accordion>` | Keywords: troubleshooting, FAQ, frequently asked, advanced, common issues, known issues, error codes, walkthrough, step by step, breakdown. |
| Paragraph that starts with `Deprecated:`, `Important:`, `Notice:`, or `Alert:` | `<Banner>` | `Notice:` becomes an info banner. The other three become warnings. |
| Paragraph that starts with `Need help?`, `Questions?`, `Support`, `Contact us`, `Get help`, `Need assistance`, `Stuck?`, or `Having trouble?` | `<Card>` with an icon | Picks the icon from the title and the text. |
| Markdown image | `<Frame>` around an `<img>` tag | Empty alt text becomes "Documentation image". |
| Link to `/api/#operation/NAME` | Link to `/api-reference/NAME` | Applies to those links only. |
| Relative link to a `.md` or `.mdx` file | Root-relative link without the extension | Links that resolve outside the input directory stay as written. |

### Callouts

The tool reads the leading label of a blockquote and picks the matching component. This input:

```markdown
> **Warning:** This change can't be undone.
> Back up your files first.
```

becomes this output:

```mdx
<Warning>
**Warning:** This change can't be undone.
Back up your files first.
</Warning>
```

### Steps

Each numbered item becomes a step. The title is the first sentence, and the body keeps the full text, so the first sentence appears twice. This input:

```markdown
1. Run the install command. This downloads the package and its dependencies.
2. Open the settings file and set the project name.
```

becomes this output:

```mdx
<Steps>
  <Step title="Run the install command">
  Run the install command. This downloads the package and its dependencies.
  </Step>
  <Step title="Open the settings file and set the project name">
  Open the settings file and set the project name.
  </Step>
</Steps>
```

### Tabs

Labelled blocks that sit next to each other form one tab group. This input:

```markdown
JavaScript:
const api = require('api');

Python:
import api
```

becomes this output:

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

## Known limits

The tool handles the patterns above and nothing else. These limits matter most when you plan a migration.

- The tool doesn't convert Docusaurus syntax. Admonitions that start with `:::` and imports from `@theme` stay as written. A test on the `website/docs` folder of the Docusaurus repository (89 files, October 25, 2026) converted every file without errors. Still, 71 files kept their `:::` admonitions and 42 kept their Docusaurus imports.
- The tool treats every blockquote as a callout. A plain quotation becomes `<Info>`, so review your quotes after you convert.
- A step title that contains inline HTML, such as `<em>`, triggers a validation warning.
- Validation checks for unclosed or mismatched tags. It doesn't check how Mintlify renders the page, so preview the converted site before you publish it.
- The tool rejects input files over 1 MiB. It skips symlinks and `file:` images, and it prints a warning for each one.

## Options

The table below lists the options you'll use most. Run `mintlify-convert --help` for the brand color, topbar, and social link options.

| Option | What it does |
| --- | --- |
| `-o`, `--output` | Sets the output file or directory. |
| `--generate-config` | Writes `docs.json` in the output directory. |
| `--legacy-mint-json` | With `--generate-config`, writes `mint.json` instead. |
| `--sort-pages` | Sorts pages alphabetically within each navigation group. |
| `--validate` | Checks the output for unclosed or mismatched tags. |
| `--download-assets` | Copies images from inside the input directory to `/images`. |
| `--icon`, `--mode` | Adds an icon or a mode, such as `wide`, to each page's frontmatter. |
| `--project-name` | Sets the project name in the generated config. |
| `--verbose` | Shows detailed error messages. |

The `--generate-mint-json` option is a deprecated alias for `--generate-config --legacy-mint-json`.

## More documentation

The `docs/` folder holds four guides:

- [Getting started](docs/getting-started.mdx): install and first conversion
- [API reference](docs/api-reference.mdx): the command line and the Python API
- [Component mapping](docs/component-mapping.mdx): how each pattern converts
- [Troubleshooting](docs/troubleshooting.mdx): common problems and fixes

## Develop

Clone the repository, install the development dependencies, and run the tests:

```bash
git clone https://github.com/Olamideod/mintlify-convert.git
cd mintlify-convert
pip install -e ".[dev]"
pytest tests/ -v --cov=mintlify_convert
```

The project uses black, flake8, and mypy for code quality:

```bash
black mintlify_convert/
flake8 mintlify_convert/
mypy mintlify_convert/
```

The file `agent.md` holds the Mintlify writing rules behind the component choices.

## Roadmap

None of these features exist yet. The first two come from the limits above.

- Docusaurus to Mintlify conversion
- GitBook to Mintlify conversion
- Incremental conversion of changed files only
- Parallel processing for large docs
- Migration reports
- Custom component plugins

## Contribute

Open an issue before you start a large change. For a small fix, fork the repository, create a branch, run `pytest tests/`, and open a pull request. Report bugs in [GitHub Issues](https://github.com/Olamideod/mintlify-convert/issues).

## License

MIT. Read the [LICENSE](LICENSE) file for details.