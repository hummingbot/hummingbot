# mdast-util-toc

[![Build][build-badge]][build]
[![Coverage][coverage-badge]][coverage]
[![Downloads][downloads-badge]][downloads]
[![Chat][chat-badge]][chat]
[![Sponsors][sponsors-badge]][collective]
[![Backers][backers-badge]][collective]

Generate a Table of Contents from **[mdast][]** trees.

## Installation

[npm][]:

```bash
npm install mdast-util-toc
```

## Usage

Dependencies:

```javascript
var util = require('util')
var u = require('unist-builder')
var toc = require('mdast-util-toc')
```

Given a mdast tree:

```javascript
var tree = u('root', [
  u('heading', {depth: 1}, [u('text', 'Alpha')]),
  u('heading', {depth: 2}, [u('text', 'Bravo')]),
  u('heading', {depth: 3}, [u('text', 'Charlie')]),
  u('heading', {depth: 2}, [u('text', 'Delta')])
])
```

Yields:

```javascript

{ index: null,
  endIndex: null,
  map: 
   { type: 'list',
     ordered: false,
     spread: true,
     children: 
      [ { type: 'listItem', loose: true, spread: true, children: [Array] } ] } }
```

## API

### `toc(node[, options])`

Generate a Table of Contents from a Markdown document.

Looks for the first heading matching `options.heading` (case insensitive,
supports alt/title attributes for links and images too), and returns a table
of contents for all following headings.
If no `heading` is specified, creates a table of contents for all headings in
`node`.

Links to headings are based on GitHub’s style.
Only top-level headings (those not in blockquotes or lists), are used.
(Change this default behavior by using option `parents` as described below)
The given node is not modified.

##### `options`

###### `options.heading`

Heading to look for (`string`), wrapped in `new RegExp('^(' + value + ')$', 'i')`.

###### `options.maxDepth`

Maximum heading depth to include in the table of contents (`number`, default:
`6`),
This is inclusive, thus, when set to `3`, level three headings, are included
(those with three hashes, `###`).

###### `options.tight`

Whether to compile list-items tightly (`boolean?`, default: `false`).

###### `options.parents`

Allows headings to be children of certain node types.
Internally, it uses
[unist-util-is](https://github.com/syntax-tree/unist-util-is) to check.
Hence all types that can be passed in as first parameter can be used here,
including `Function`, `string`, `Object` and `Array.<Test>`.
Check
[documentation](https://github.com/syntax-tree/unist-util-is#readme)
for details.
(default: the first parameter `node`, which only allows top-level headings)

Example:

```json
{
  "parents": ["root", "blockquote"]
}
```

This would allow headings under either `root` or `blockquote` to be used.

##### Returns

An object representing the table of contents.

###### Properties

*   `index` (`number?`)
    — Position of the `heading` in `node`.  `-1` if no heading
    was found, `null` if no heading was given
*   `endIndex` (`number?`)
    — Position of the last node after `heading` before the TOC starts.
    `-1` if no heading was found, `null` if no heading was given,
    same as `index` if there are no nodes between `heading` and the
    first heading in the TOC
*   `map` (`Node?`)
    — List node representing the generated table of contents.
    `null` if no table of contents could be created, either because
    `heading` didn’t exist, or because no following headings were found

## Contribute

See [`contributing.md` in `syntax-tree/mdast`][contributing] for ways to get
started.

This organisation has a [Code of Conduct][coc].  By interacting with this
repository, organisation, or community you agree to abide by its terms.

## License

[MIT][license] © [Jonathan Haines][author]

<!-- Definitions -->

[build-badge]: https://img.shields.io/travis/syntax-tree/mdast-util-toc.svg

[build]: https://travis-ci.org/syntax-tree/mdast-util-toc

[coverage-badge]: https://img.shields.io/codecov/c/github/syntax-tree/mdast-util-toc.svg

[coverage]: https://codecov.io/github/syntax-tree/mdast-util-toc

[downloads-badge]: https://img.shields.io/npm/dm/mdast-util-toc.svg

[downloads]: https://www.npmjs.com/package/mdast-util-toc

[chat-badge]: https://img.shields.io/badge/join%20the%20community-on%20spectrum-7b16ff.svg

[chat]: https://spectrum.chat/unified/remark

[sponsors-badge]: https://opencollective.com/unified/sponsors/badge.svg

[backers-badge]: https://opencollective.com/unified/backers/badge.svg

[collective]: https://opencollective.com/unified

[npm]: https://docs.npmjs.com/cli/install

[license]: license

[author]: https://barrythepenguin.github.io

[mdast]: https://github.com/syntax-tree/mdast

[contributing]: https://github.com/syntax-tree/mdast/blob/master/contributing.md

[coc]: https://github.com/syntax-tree/mdast/blob/master/code-of-conduct.md
