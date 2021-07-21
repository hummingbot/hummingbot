# `pretty-quick`

[![Travis](https://img.shields.io/travis/azz/pretty-quick.svg?style=flat-square)](https://travis-ci.org/azz/pretty-quick)
[![Prettier](https://img.shields.io/badge/code_style-prettier-ff69b4.svg?style=flat-square)](https://github.com/prettier/prettier)
[![npm](https://img.shields.io/npm/v/pretty-quick.svg?style=flat-square)](https://npmjs.org/pretty-quick)
[![semantic-release](https://img.shields.io/badge/%20%20%F0%9F%93%A6%F0%9F%9A%80-semantic--release-e10079.svg?style=flat-square)](https://github.com/semantic-release/semantic-release)
[![License](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](LICENSE)

> Get Pretty Quick

Runs [Prettier](https://prettier.io) on your changed files.

![demo](./img/demo.gif)

Supported source control managers:

- Git
- Mercurial

## Install

With `yarn`:

```shellsession
yarn add --dev prettier pretty-quick
```

With `npm`:

```shellsession
npm install --save-dev prettier pretty-quick
```

## Usage

With `yarn`:

```shellsession
yarn pretty-quick
```

With [`npx`](https://npm.im/npx):

```shellsession
npx -p prettier@latest -p pretty-quick pretty-quick
```

> Note: You can (_should_) change `latest` to a specific version of Prettier.

With `npm`:

1. Add `"pretty-quick": "pretty-quick"` to the `"scripts"` section of `package.json`.
2. `npm run pretty-quick`

## Pre-Commit Hook

You can run `pretty-quick` as a pre-commit hook using [`husky`](https://github.com/typicode/husky).

> For Mercurial have a look at [`husky-hg`](https://github.com/TobiasTimm/husky-hg)

```shellstream
yarn add --dev husky
```

In `package.json`, add:

```json
"husky": {
  "hooks": {
    "pre-commit": "pretty-quick --staged"
  }
}
```

![demo](./img/precommit.gif)

## CLI Flags

### `--staged` (only git)

Pre-commit mode. Under this flag only staged files will be formatted, and they will be re-staged after formatting.

Partially staged files will not be re-staged after formatting and pretty-quick will exit with a non-zero exit code. The intent is to abort the git commit and allow the user to amend their selective staging to include formatting fixes.

### `--no-restage` (only git)

Use with the `--staged` flag to skip re-staging files after formatting.

### `--branch`

When not in `staged` pre-commit mode, use this flag to compare changes with the specified branch. Defaults to `master` (git) / `default` (hg) branch.

### `--pattern`

Filters the files for the given [minimatch](https://github.com/isaacs/minimatch) pattern.  
For example `pretty-quick --pattern "**/*.*(js|jsx)"` or `pretty-quick --pattern "**/*.js" --pattern "**/*.jsx"`

### `--verbose`

Outputs the name of each file right before it is proccessed. This can be useful if Prettier throws an error and you can't identify which file is causing the problem.

### `--bail`

Prevent `git commit` if any files are fixed.

### `--check`

Check that files are correctly formatted, but don't format them. This is useful on CI to verify that all changed files in the current branch were correctly formatted.

### `--no-resolve-config`

Do not resolve prettier config when determining which files to format, just use standard set of supported file types & extensions prettier supports. This may be useful if you do not need any customization and see performance issues.

By default, pretty-quick will check your prettier configuration file for any overrides you define to support formatting of additional file extensions.

Example `.prettierrc` file to support formatting files with `.cmp` or `.page` extensions as html.

```
{
    "printWidth": 120,
    "bracketSpacing": false,
    "overrides": [
        {
            "files": "*.{cmp,page}",
            "options": {"parser": "html"}
        }
    ],
}
```

<!-- Undocumented = Unsupported :D

### `--config`

Path to a `.prettierrc` file.

### `--since`

A SCM revision such as a git commit hash or ref.

For example `pretty-quick --since HEAD` will format only staged files.

-->

### `--ignore-path`

Check an alternative file for ignoring files with the same format as [`.prettierignore`](https://prettier.io/docs/en/ignore#ignoring-files).
For example `pretty-quick --ignore-path=.gitignore`

## Configuration and Ignore Files

`pretty-quick` will respect your [`.prettierrc`](https://prettier.io/docs/en/configuration), [`.prettierignore`](https://prettier.io/docs/en/ignore#ignoring-files), and [`.editorconfig`](http://editorconfig.org/) files if you don't use `--ignore-path` . Configuration files will be found by searching up the file system. `.prettierignore` files are only found from the repository root and the working directory that the command was executed from.
