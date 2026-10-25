# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

No release has been tagged or published yet. The entries below describe the v2.0 work in progress.

### Added
- Mintlify component output: Warning, Note, Tip, Info and Check callouts, Steps, Tabs, Cards, Accordion (keyword heuristic on H3 titles), Banner (narrow prefix match) and Frame-wrapped images
- Navigation generation with nested groups from the folder structure; "Getting Started" first, then alphabetical; optional `--sort-pages`
- `docs.json` generation (`--generate-config`) and legacy `mint.json` generation (`--legacy-mint-json`)
- Asset handling: images are copied only with `--download-assets` and only from inside the input directory
- MDX validation with error reporting
- Command-line interface with branding options for the generated config file
- Project restructure into a package, test suite with fixtures, examples, CI workflows and pre-commit configuration

### Changed
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
