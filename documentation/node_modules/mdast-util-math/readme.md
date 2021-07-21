# mdast-util-math

[![Build][build-badge]][build]
[![Coverage][coverage-badge]][coverage]
[![Downloads][downloads-badge]][downloads]
[![Size][size-badge]][size]
[![Sponsors][sponsors-badge]][collective]
[![Backers][backers-badge]][collective]
[![Chat][chat-badge]][chat]

Extension for [`mdast-util-from-markdown`][from-markdown] and/or
[`mdast-util-to-markdown`][to-markdown] to support math in **[mdast][]**.
When parsing (`from-markdown`), must be combined with
[`micromark-extension-math`][extension].

You probably shouldn’t use this package directly, but instead use
[`remark-math`][remark-math] with **[remark][]**.

## Install

[npm][]:

```sh
npm install mdast-util-math
```

## Use

Say we have the following file, `example.md`:

```markdown
Lift($L$) can be determined by Lift Coefficient ($C_L$) like the following equation.

$$
L = \frac{1}{2} \rho v^2 S C_L
$$
```

And our script, `example.js`, looks as follows:

```js
var fs = require('fs')
var fromMarkdown = require('mdast-util-from-markdown')
var toMarkdown = require('mdast-util-to-markdown')
var syntax = require('micromark-extension-math')
var math = require('mdast-util-math')

var doc = fs.readFileSync('example.md')

var tree = fromMarkdown(doc, {
  extensions: [syntax],
  mdastExtensions: [math.fromMarkdown]
})

console.log(tree)

var out = toMarkdown(tree, {extensions: [math.toMarkdown]})

console.log(out)
```

Now, running `node example` yields (positional info removed for brevity):

```js
{
  type: 'root',
  children: [
    {
      type: 'paragraph',
      children: [
        {type: 'text', value: 'Lift('},
        {type: 'inlineMath', value: 'L', data: {/* … */}},
        {type: 'text', value: ') can be determined by Lift Coefficient ('},
        {type: 'inlineMath', e: 'C_L', data: {/* … */}},
        {type: 'text', value: ') like the following equation.'}
      ]
    },
    {type: 'math', meta: null, value: 'L = \\frac{1}{2} \\rho v^2 S C_L', data: {/* … */}}
  ]
}
```

```markdown
Lift($L$) can be determined by Lift Coefficient ($C_L$) like the following equation.

$$
L = \frac{1}{2} \rho v^2 S C_L
$$
```

## API

### `math.fromMarkdown`

### `math.toMarkdown`

> Note: the separate extensions are also available at
> `mdast-util-math/from-markdown` and
> `mdast-util-math/to-markdown`.

Support math.
These exports are extensions, respectively for
[`mdast-util-from-markdown`][from-markdown] and
[`mdast-util-to-markdown`][to-markdown].

## Related

*   [`remarkjs/remark`][remark]
    — markdown processor powered by plugins
*   [`remarkjs/remark-math`][remark-math]
    — remark plugin to support math
*   [`micromark/micromark`][micromark]
    — the smallest commonmark compliant markdown parser that exists
*   [`micromark/micromark-extension-math`][extension]
    — micromark extension to parse math
*   [`syntax-tree/mdast-util-from-markdown`][from-markdown]
    — mdast parser using `micromark` to create mdast from markdown
*   [`syntax-tree/mdast-util-to-markdown`][to-markdown]
    — mdast serializer to create markdown from mdast

## Contribute

See [`contributing.md` in `syntax-tree/.github`][contributing] for ways to get
started.
See [`support.md`][support] for ways to get help.

This project has a [code of conduct][coc].
By interacting with this repository, organization, or community you agree to
abide by its terms.

## License

[MIT][license] © [Titus Wormer][author]

<!-- Definitions -->

[build-badge]: https://img.shields.io/travis/syntax-tree/mdast-util-math.svg

[build]: https://travis-ci.org/syntax-tree/mdast-util-math

[coverage-badge]: https://img.shields.io/codecov/c/github/syntax-tree/mdast-util-math.svg

[coverage]: https://codecov.io/github/syntax-tree/mdast-util-math

[downloads-badge]: https://img.shields.io/npm/dm/mdast-util-math.svg

[downloads]: https://www.npmjs.com/package/mdast-util-math

[size-badge]: https://img.shields.io/bundlephobia/minzip/mdast-util-math.svg

[size]: https://bundlephobia.com/result?p=mdast-util-math

[sponsors-badge]: https://opencollective.com/unified/sponsors/badge.svg

[backers-badge]: https://opencollective.com/unified/backers/badge.svg

[collective]: https://opencollective.com/unified

[chat-badge]: https://img.shields.io/badge/chat-discussions-success.svg

[chat]: https://github.com/syntax-tree/unist/discussions

[npm]: https://docs.npmjs.com/cli/install

[license]: license

[author]: https://wooorm.com

[contributing]: https://github.com/syntax-tree/.github/blob/HEAD/contributing.md

[support]: https://github.com/syntax-tree/.github/blob/HEAD/support.md

[coc]: https://github.com/syntax-tree/.github/blob/HEAD/code-of-conduct.md

[mdast]: https://github.com/syntax-tree/mdast

[remark]: https://github.com/remarkjs/remark

[remark-math]: https://github.com/remarkjs/remark-math

[from-markdown]: https://github.com/syntax-tree/mdast-util-from-markdown

[to-markdown]: https://github.com/syntax-tree/mdast-util-to-markdown

[micromark]: https://github.com/micromark/micromark

[extension]: https://github.com/micromark/micromark-extension-math
