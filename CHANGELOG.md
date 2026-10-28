# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.1.0] - 2026-10-26

### Added
- Diataxis navigation (`--structure diataxis`, the default for `--generate-config`): a Documentation tab with Get started, Tutorials, How-to guides and Concepts, and a separate API reference tab. `--explain-ia` shows each decision and `--ia-config` overrides it
- Images from the Docusaurus `static` folder (`/img/...`, `@site/static/...`, `pathname:///...`) are copied to `/images` by default; `--static-dir` and `--no-assets` control this. Image titles become Frame captions, and `<img>` attributes are kept
- `<ThemedImage>` and GitHub-style light/dark images become one Frame with light and dark `<img>` tags
- Lucide icons: `docs.json` sets `icons.library` and every icon written is validated against the Lucide list
- `mdx-code-block` fences are unwrapped, so Tabs around code fences convert; `npm2yarn` fences become `CodeGroup`; `Admonition`, `CodeBlock` with literal strings, `LiteYouTubeEmbed`, `DocCardList`, `URLPath` and `FilePath` convert; `BrowserWindow`, `Zoom` and `APITable` unwrap
- Unknown components become `TODO(mintlify-convert)` comments instead of breaking the Mintlify page
- Partials (`_file.mdx`) become `/snippets` files and stay out of the navigation
- Site-wide link handling: renamed pages with redirects, `slug`/`id` routes, the `/docs` prefix, custom heading ids mapped to Mintlify anchors, reference-style link definitions, links from the docs root, `--site-url` for links outside the docs
- `_category_.yml` labels and positions feed group names and order
- `--validate` also checks the converted site for dead links, anchors, images and `docs.json` entries
- Docusaurus conversion: `:::` admonitions (nested, with titles), `<Tabs>`/`<TabItem>`, `<details>`, `<Translate>`, `<Link>`, code block `showLineNumbers`, `{1,3-5}` and `highlight-*` magic comments, HTML comments, heading ids, imports, and Docusaurus-only frontmatter keys
- `<Danger>` callout for danger blockquotes and admonitions
- Warnings for removed imports that are still used, for components Mintlify does not provide, and for dropped heading ids
- Navigation nests folders as subgroups and orders pages by `sidebar_position`
- Mintlify component output: Warning, Note, Tip, Info and Check callouts, Steps, Tabs, Cards, Accordion (keyword heuristic on H3 titles), Banner (narrow prefix match) and Frame-wrapped images
- Navigation generation with nested groups from the folder structure; "Getting Started" first, then alphabetical; optional `--sort-pages`
- `docs.json` generation (`--generate-config`) and legacy `mint.json` generation (`--legacy-mint-json`)
- Asset handling: images are copied only with `--download-assets` and only from inside the input directory
- MDX validation with error reporting
- Command-line interface with branding options for the generated config file
- Project restructure into a package, test suite with fixtures, examples, CI workflows and pre-commit configuration

### Fixed
- The package no longer fails to import on Python 3.10 and 3.11 (a backslash inside an f-string expression is a syntax error before 3.12)
- Files whose names differ only by case, such as `Case.md` and `case.md`, are now kept apart on case-sensitive file systems; before, both claimed the same output name
- Converting the tool's own output is now stable: blank lines left where a component was removed collapse to one, so a second pass changes nothing
- Review round: unknown components keep nested content; themed images inside lists stay in their step; YAML block scalars and empty titles; crashes on bad `_category_.yml` / `--ia-config`; case-colliding file names; duplicate-slug warnings; hidden folders skipped; links with parentheses, spaces, percent-encoding or an image label; Docusaurus-hook exports and `require()` links; npm2yarn for `-g` and `&&` chains; lists of questions stay plain lists

### Changed
- Page titles drop Markdown (`` `docusaurus.config.js` `` becomes `docusaurus.config.js`), plain titles that YAML would misread are quoted, and the title leads the frontmatter. A page with no title is named after its file
- File names with dots are renamed (`docusaurus.config.js.mdx` to `docusaurus-config-js.mdx`); colliding names get a numeric suffix
- Group names keep acronyms and brands (`API`, `CLI`, `ESLint`, `i18n` as Internationalization)
- Help-card icons use Lucide names (`circle-help`, `book-open`)
- Descriptions no longer contain inline code ticks, images or reference links
- Step titles no longer contain tag-like text such as `<em>`
- Links and images accept single-quoted titles
- `--generate-mint-json` is deprecated; it is an alias for `--generate-config --legacy-mint-json`
- Minimum supported Python version is 3.10
- Conversion is idempotent, and the output path may not equal or sit inside the input path
- Input files larger than 1 MiB are rejected with an error
- Navigation groups are ordered "Getting Started", then "Documentation", then the rest alphabetically
- Accordions are created only for H3 headings containing troubleshooting, FAQ, frequently asked, advanced, common issues, known issues, error codes, walkthrough, step by step or breakdown, and end at the next heading of any level
- One numbered list becomes one `<Steps>` block; it continues across blank lines and code fences or indented content between items
- Step titles are plain text and end at a clause or word boundary at about 80 characters
- Consecutive language-labelled blocks (three or more included) form one `<Tabs>` group
- Relative links that resolve outside the input directory are left unchanged
- Callouts, banners and step lists that start with a code fence are left unconverted; banners and help cards only match at the start of a paragraph
- Symlinked input files and `file:` image sources are skipped with a warning on stderr; the exit status stays 0
- `--validate` no longer reports code-block content as unclosed tags

### Security
- Images are copied only with `--download-assets`, only from inside the input directory, and only if they are common image types; absolute, `file:`, `data:` and `//` sources and symlinks are not copied, and copied files keep only their base name
- The output path may not equal or sit inside the input path
- Input files over 1 MiB are rejected, symlinked input files are skipped, and link and image patterns are length-bounded

### Removed
- `--use-ai-description` flag and the placeholder AI description code (AI descriptions are future work)
- Legacy standalone script `mintlify_convert.py`
- Documentation of flags that never existed (`--no-validate`, `--parallel`, `--workers`, `--no-download-assets`) and of environment variables and exit codes the code does not implement

### Fixed
- Pathological input no longer causes slow conversion: 20,000 consecutive `Python:` label lines and 100,000 repeated `[a](` sequences each convert in under a second in a local run
- A page whose first prose line is a tab label no longer uses it as the description
- Broken links between documentation pages and placeholder URLs in the README and guides

## Earlier history (dates unverified; carried over from the original file)

The repository contains a single commit (2025-10-13). The release dates and the v1.x history below could not be verified and are kept as originally written, except for the two lines noted under 2.0.0.

### [2.0.0] - 2024-01-01

#### Added
- Enhanced Mintlify component support (Accordion, Tabs, Banner, Callout)
- Advanced navigation generation with nested groups
- Asset handling and image copying
- MDX validation with detailed error reporting
- ~~AI description generation (placeholder for OpenAI integration)~~ Not implemented; the placeholder was removed (see Unreleased)
- Comprehensive command-line interface
- Custom branding options for mint.json
- ~~Parallel processing support (future feature)~~ Not implemented; never available

#### Changed
- Complete rewrite from v1.x
- Improved component mapping accuracy
- Enhanced error handling and validation
- Better support for complex documentation structures

#### Fixed
- Unclosed tag detection in MDX validation
- Image path resolution issues
- Navigation structure generation
- Component conversion edge cases

### [1.0.0] - 2023-12-01

#### Added
- Initial release
- Basic MDX to Mintlify conversion
- Core component mapping (Callouts, Steps, Cards)
- Simple navigation generation
- Command-line interface
- Basic validation

#### Features
- Convert blockquotes to Callout components
- Transform numbered lists to Steps
- Generate help sections as Cards
- Create basic mint.json files
- Process single files and directories
