# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Project restructure with proper package organization
- Comprehensive test suite with fixtures
- Examples directory with sample conversions
- Complete documentation
- GitHub Actions workflows for CI/CD
- Pre-commit hooks configuration

## [2.0.0] - 2024-01-01

### Added
- Enhanced Mintlify component support (Accordion, Tabs, Banner, Callout)
- Advanced navigation generation with nested groups
- Asset handling and image copying
- MDX validation with detailed error reporting
- AI description generation (placeholder for OpenAI integration)
- Comprehensive command-line interface
- Custom branding options for mint.json
- Parallel processing support (future feature)

### Changed
- Complete rewrite from v1.x
- Improved component mapping accuracy
- Enhanced error handling and validation
- Better support for complex documentation structures

### Fixed
- Unclosed tag detection in MDX validation
- Image path resolution issues
- Navigation structure generation
- Component conversion edge cases

## [1.0.0] - 2023-12-01

### Added
- Initial release
- Basic MDX to Mintlify conversion
- Core component mapping (Callouts, Steps, Cards)
- Simple navigation generation
- Command-line interface
- Basic validation

### Features
- Convert blockquotes to Callout components
- Transform numbered lists to Steps
- Generate help sections as Cards
- Create basic mint.json files
- Process single files and directories
