## [v0.7.0] - May 20, 2015

 * Automatically prettifies JSON files.

## [v0.6.2] - November 10, 2014

 * Add *repository* field to `package.json`. No functional changes.

## [v0.6.1] - August 4, 2014

 * Fix `--numbers --debug` adding line numbers to debug info.
 * Fix `--numbers` putting an extra line
 * Always assume that small files (<24 lines) don't need a pager.
 * Don't wrap long lines when using the pager.

## [v0.6.0] - August 4, 2014

 * Add the `--numbers` option for line numbers.

## [v0.5.1] - August 3, 2014

 * Fix the pager not being on by default.

## [v0.5.0] - July 31, 2014

 * Change comment color to cyan.
 * Add colors for javadoc tags.
 * (Internal) documentations and tests.

### [v0.4.1]

 * JSON: prevent symbols (`{ }`) from being colorized as green.

### [v0.4.0]

 * Add colors for javadoc comments.
 * Add support for Ruby string interpolation.
 * Make the output of the undocumented `--debug` switch more useful.
 * (Internal) Refactors to tests, color schemes, and many others.

### [v0.3.2]

 * Add colors for diffs (`--lang diff`).

## [v0.3.1] - July 30, 2014

 * Fix piping not working.

### [v0.3.0]

 * Automatically page the output if the file is long.
 * Throw less-verbose error messages.

### [v0.2.3]

 * Add colors for Markdown files (`--lang markdown`).
 * Add colors for CSS tokens (`--lang css`).
 * Add colors for C pre-processor directives.

### [v0.2.2]

 * Fix `--lang` not working properly.

### [v0.2.0]

 * Add `--languages` option to list available languages.
 * Rename `--type` to `--lang`.

## v0.1.0 - July 30, 2014

 * Initial release.

[v0.7.0]: https://github.com/git@github.com:rstacruz/hicat/compare/v0.6.2...v0.7.0
[v0.6.2]: https://github.com/git@github.com:rstacruz/hicat/compare/v0.6.1...v0.6.2
[v0.6.1]: https://github.com/git@github.com:rstacruz/hicat/compare/v0.6.0...v0.6.1
[v0.6.0]: https://github.com/git@github.com:rstacruz/hicat/compare/v0.5.1...v0.6.0
[v0.5.1]: https://github.com/git@github.com:rstacruz/hicat/compare/v0.5.0...v0.5.1
[v0.5.0]: https://github.com/git@github.com:rstacruz/hicat/compare/v0.4.1...v0.5.0
[v0.4.1]: https://github.com/git@github.com:rstacruz/hicat/compare/v0.4.0...v0.4.1
[v0.4.0]: https://github.com/git@github.com:rstacruz/hicat/compare/v0.3.2...v0.4.0
[v0.3.2]: https://github.com/git@github.com:rstacruz/hicat/compare/v0.3.1...v0.3.2
[v0.3.1]: https://github.com/git@github.com:rstacruz/hicat/compare/v0.3.0...v0.3.1
[v0.3.0]: https://github.com/git@github.com:rstacruz/hicat/compare/v0.2.3...v0.3.0
[v0.2.3]: https://github.com/git@github.com:rstacruz/hicat/compare/v0.2.2...v0.2.3
[v0.2.2]: https://github.com/git@github.com:rstacruz/hicat/compare/v0.3.0...v0.2.2
[v0.2.0]: https://github.com/git@github.com:rstacruz/hicat/compare/v0.1.0...v0.2.0
