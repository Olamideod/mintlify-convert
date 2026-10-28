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
| Markdown image or `<img>` | `<Frame>` around an `<img>` tag | Copies the file to `/images`, including `/img/...` paths from the Docusaurus `static` folder. An image title becomes the Frame `caption`. Empty alt text becomes the file name. `<img>` attributes such as `width` stay. |
| `<ThemedImage>` and `#gh-light-mode-only` / `#gh-dark-mode-only` image pairs | One `<Frame>` with a light and a dark `<img>` | Uses Mintlify's `block dark:hidden` and `hidden dark:block` classes. |
| Code fence tagged `npm2yarn` | `<CodeGroup>` with npm, yarn and pnpm tabs | Converts `npm install`, `npm run`, and `npx`. |
| ` ```mdx-code-block ` fence | Its contents as plain MDX | Docusaurus uses these fences to open a `<Tabs>` around ordinary code fences. |
| `<BrowserWindow>`, `<Zoom>`, `<APITable>` | Removed, content kept | Mintlify zooms images and styles tables itself. |
| `<Admonition type title>` | `<Note>`, `<Tip>`, ... | Same type mapping as `:::` admonitions. |
| `<CodeBlock language>{'text'}</CodeBlock>` | Code fence | Only for literal strings. |
| `<LiteYouTubeEmbed id>` | `<iframe>` | |
| `<DocCardList />` | `<CardGroup>` of `<Card>` links to the pages in that folder | |
| `<URLPath />`, `<FilePath />` | The page URL and source path in inline code | |
| Any other component | A `{/* TODO(mintlify-convert) */}` comment | Mintlify fails a page that uses an undefined component. Children that are plain content stay. |
| `_partial.mdx` imported by other pages | A file in `/snippets` and an import of it | The partial is not a page and stays out of the navigation. |
| Docusaurus admonition, `:::tip[Title]` to `:::` | `<Note>`, `<Tip>`, `<Info>`, `<Warning>`, `<Danger>`, or `<Check>` | `caution` becomes a warning and `success` becomes a check. The title becomes a bold first line. Nested admonitions work. |
| Docusaurus `<Tabs>` with `<TabItem value label default>` | `<Tabs>` with one `<Tab title>` for each item | Reads labels from `label` or from a `values` prop. `default` and `defaultValue` become `defaultTabIndex`. Drops `groupId` and `queryString`. |
| `<details><summary>` | `<Accordion title>` | `<details open>` becomes `defaultOpen`. |
| Code fence with `showLineNumbers`, `{1,3-5}`, or `// highlight-next-line`, `highlight-start`, and `highlight-end` comments | Fence with `lines` and `highlight={1,3-5}` | Removes the comment lines and highlights the lines they marked. Keeps `title="..."`. |
| `import` line | Removed | Mintlify only imports from `/snippets/`. The tool warns when the page still uses a removed component. |
| `<!-- comment -->` | `{/* comment */}` | MDX rejects HTML comments. |
| Heading id, `## Title {#id}` | `## Title` | Mintlify builds its own anchors, so links to `#id` are rewritten to the anchor Mintlify builds. |
| `<Translate>`, `<Link to>`, `<TOCInline>`, `<DocCardList>` | Plain text, a Markdown link, or removed | |
| Frontmatter from Docusaurus | Mintlify frontmatter | `sidebar_label` becomes `sidebarTitle`. `sidebar_position`, `slug`, `id`, `tags`, and other Docusaurus-only keys are dropped. `sidebar_position` still orders the pages in `docs.json`. |
| Link to `/api/#operation/NAME` | Link to `/api-reference/NAME` | Applies to those links only. |
| Relative link to a `.md` or `.mdx` file | Root-relative link without the extension | Resolves from the file, then from the docs root, as Docusaurus does. Also rewrites `[ref]: path` definitions, `slug` routes and the `/docs` prefix. Links that resolve outside the input directory stay as written. |
| Link to a page outside the docs, such as `/blog/...` | Unchanged, or absolute with `--site-url` | The tool warns about each page that has such links. |
| File name with dots, `docusaurus.config.js.mdx` | `docusaurus-config-js.mdx` | The title stays `docusaurus.config.js`, and `docs.json` gets a redirect from the old URL. |
| Markdown in a title, `` # `docusaurus.config.js` `` | Plain title | Mintlify prints titles as written. |

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

## Navigation and page structure

With `--generate-config` the tool writes `docs.json` and arranges the pages by the [Diataxis](https://diataxis.fr) framework, whatever the source folders looked like. The default layout has two tabs:

- **Documentation** has the groups Get started, Tutorials, How-to guides, and Concepts. Folders inside a group become subgroups, with one-page folders flattened into their parent.
- **API reference** holds the reference pages: API, CLI, and configuration material, with subgroups from the source folders.

The tool decides where a page goes from its folder names, file name, title, and the shape of the content: numbered steps, tables, and many headings named after code. Run with `--explain-ia` to see the section chosen for each page and the reason. If the tool gets a page wrong, move it with an IA config file:

```json
{
  "pages": {
    "configuration": {"section": "start"},
    "guides/markdown-features/*": {"group": "Markdown", "position": 3}
  },
  "groups": {"Miscellaneous": "Tooling"},
  "tabs": {"API reference": "API"}
}
```

```bash
mintlify-convert docs/ -o out/ --generate-config --ia-config ia.json
```

The sections are `start`, `tutorial`, `howto`, `concept`, and `reference`. Page patterns are globs over the output path without the extension. Use `--structure folders` to keep the source folders as navigation groups instead.

The generated `docs.json` also:

- Sets `icons.library` to `lucide` and gives each tab and top-level group a Lucide icon. Every icon the tool writes is checked against the Lucide icon list.
- Reads `label` and `position` from Docusaurus `_category_.yml` files.
- Adds `redirects` for pages whose file name changed.
- Turns on the contextual menu (copy, view, ChatGPT, Claude).

Images are copied to `/images` by default when you convert a directory. Use `--no-assets` to leave paths as written. The tool looks for the Docusaurus `static` folder next to the docs folder, or at the path you give to `--static-dir`.

With `--validate`, the tool also checks the converted site for links, anchors, images and `docs.json` entries that point at nothing.

## Known limits

The tool handles the patterns above and nothing else. These limits matter most when you plan a migration.

- Docusaurus support covers the syntax in the table above. Custom React components from your Docusaurus site, such as `<ColorGenerator>` or `<PlaygroundCardsRow>`, have no Mintlify equivalent. The tool replaces each with a `TODO(mintlify-convert)` comment and warns, so rebuild them by hand. On the `website/docs` folder of the Docusaurus repository (89 files), every file converts, the tool's own checks find no unclosed tags, and the only dead links or anchors are two that are already broken in the Docusaurus source.
- Links to pages outside the input directory, such as `/blog/...` in a Docusaurus site, stay as written unless you pass `--site-url`.
- The page classifier is a heuristic. Use `--explain-ia` to review it and `--ia-config` to correct it.
- The tool treats every blockquote as a callout. A plain quotation becomes `<Info>`, so review your quotes after you convert.
- Validation checks for unclosed or mismatched tags. It doesn't check how Mintlify renders the page, so preview the converted site before you publish it.
- The tool rejects input files over 1 MiB. It skips symlinks and `file:` images, and it prints a warning for each one.

## Options

The table below lists the options you'll use most. Run `mintlify-convert --help` for the brand color, topbar, and social link options.

| Option | What it does |
| --- | --- |
| `-o`, `--output` | Sets the output file or directory. |
| `--generate-config` | Writes `docs.json` in the output directory. |
| `--legacy-mint-json` | With `--generate-config`, writes `mint.json` instead. |
| `--structure` | `diataxis` (default) or `folders`. |
| `--ia-config` | JSON file that moves pages between sections and renames groups and tabs. |
| `--explain-ia` | Prints the section chosen for each page and why. |
| `--sort-pages` | Sorts pages alphabetically within each navigation group. |
| `--validate` | Checks the output for unclosed or mismatched tags, and for dead links, anchors, and images. |
| `--no-assets` | Leaves image paths as written instead of copying the files to `/images`. |
| `--static-dir` | Folder that `/img/...` image paths resolve against. Defaults to `../static` next to the docs. |
| `--site-url` | Base URL of the old site. Links to pages outside the docs become absolute links to it. |
| `--route-prefix` | URL prefix the old site served its docs under. Defaults to `/docs` when the input folder is `docs`. |
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

The project uses black, flake8, and mypy for code quality. CI runs the tests on Python 3.10 to 3.13 and fails the build if `black --check` or flake8 report a problem, so run them before you push:

```bash
black mintlify_convert/ tests/
flake8 mintlify_convert/
mypy mintlify_convert/
```

The file `agent.md` holds the Mintlify writing rules behind the component choices.

## Roadmap

None of these features exist yet.

- GitBook to Mintlify conversion
- Incremental conversion of changed files only
- Parallel processing for large docs
- Migration reports
- Custom component plugins

## Contribute

Open an issue before you start a large change. For a small fix, fork the repository, create a branch, run `pytest tests/`, and open a pull request. Report bugs in [GitHub Issues](https://github.com/Olamideod/mintlify-convert/issues).

## License

MIT. Read the [LICENSE](LICENSE) file for details.