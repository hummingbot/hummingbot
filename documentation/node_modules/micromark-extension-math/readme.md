# micromark-extension-math

[![Build][build-badge]][build]
[![Coverage][coverage-badge]][coverage]
[![Downloads][downloads-badge]][downloads]
[![Size][size-badge]][size]
[![Sponsors][sponsors-badge]][collective]
[![Backers][backers-badge]][collective]
[![Chat][chat-badge]][chat]

**[micromark][]** extension to support math (`$C_L$`).

As there is no spec for math in markdown, this extension stays as close to
code in text and fenced code in flow in CommonMark, but using dollar signs.

This package provides the low-level modules for integrating with the micromark
tokenizer and the micromark HTML compiler.

You probably shouldn’t use the HTML parts of this package directly, but instead
use [`mdast-util-math`][mdast-util-math] with **[mdast][]**.

```markdown
Math (text) can start with one or more dollar signs, so long as they match:
With one: $\alpha$, two: $$\beta$$, or three: $$$\gamma$$$.

This is useful, because like code, typical markdown escapes don’t work.
For dollars inside math, use more dollars around it: $$\raisebox{0.25em}{$\frac
a b$}$$.

If the math starts and ends with a space (or EOL), those are removed: $$ \$ $$.

Math (flow) starts at two or more dollars:

$$
\Delta
$$

You can hide some stuff in the meta of the opening fence (but no dollars):

$$hidden information
$$

Math which doesn’t have a closing fence, still works, like fenced code:

> $$
> this is
> all math

…but at the end of their container (block quote, list item, or document), they
are closed.
```

## Install

[npm][]:

```sh
npm install micromark-extension-math
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
var micromark = require('micromark')
var math = require('micromark-extension-math')
var mathHtml = require('micromark-extension-math/html')

var doc = fs.readFileSync('example.md')

var result = micromark(doc, {
  extensions: [math],
  htmlExtensions: [mathHtml()]
})

console.log(result)
```

Now, running `node example` yields (abbreviated):

```html
<p>Lift(<span class="math math-inline"><span class="katex">…</span></span>) can be determined by Lift Coefficient (<span class="math math-inline"><span class="katex">…</span></span>) like the following equation.</p>
<div class="math math-display"><span class="katex-display"><span class="katex">…</span></span></div>
```

## API

### `html(options?)`

### `syntax`

> Note: `syntax` is the default export of this module, `html` is available at
> `micromark-extension-math/html`.

Support math.
The export of `syntax` is an extension for the micromark parser (to tokenize
math in text and flow; can be passed in `extensions`).
The export of `html` is a function that can be called with options and returns
an extension for the default HTML compiler (to compile math with [KaTeX][]; can
be passed in `htmlExtensions`).

##### `options`

Passed to [`katex.renderToString`][katex-options].
`displayMode` is overwritten by this plugin, to `false` for math in text, and
`true` for math in flow.

## Related

*   [`remarkjs/remark`][remark]
    — markdown processor powered by plugins
*   [`micromark/micromark`][micromark]
    — the smallest commonmark-compliant markdown parser that exists
*   [`syntax-tree/mdast-util-math`][mdast-util-math]
    — mdast utility to support math
*   [`syntax-tree/mdast-util-from-markdown`][from-markdown]
    — mdast parser using `micromark` to create mdast from markdown
*   [`syntax-tree/mdast-util-to-markdown`][to-markdown]
    — mdast serializer to create markdown from mdast

## Contribute

See [`contributing.md` in `micromark/.github`][contributing] for ways to get
started.
See [`support.md`][support] for ways to get help.

This project has a [code of conduct][coc].
By interacting with this repository, organization, or community you agree to
abide by its terms.

## License

[MIT][license] © [Titus Wormer][author]

<!-- Definitions -->

[build-badge]: https://img.shields.io/travis/micromark/micromark-extension-math.svg

[build]: https://travis-ci.org/micromark/micromark-extension-math

[coverage-badge]: https://img.shields.io/codecov/c/github/micromark/micromark-extension-math.svg

[coverage]: https://codecov.io/github/micromark/micromark-extension-math

[downloads-badge]: https://img.shields.io/npm/dm/micromark-extension-math.svg

[downloads]: https://www.npmjs.com/package/micromark-extension-math

[size-badge]: https://img.shields.io/bundlephobia/minzip/micromark-extension-math.svg

[size]: https://bundlephobia.com/result?p=micromark-extension-math

[sponsors-badge]: https://opencollective.com/unified/sponsors/badge.svg

[backers-badge]: https://opencollective.com/unified/backers/badge.svg

[collective]: https://opencollective.com/unified

[chat-badge]: https://img.shields.io/badge/chat-discussions-success.svg

[chat]: https://github.com/micromark/unist/discussions

[npm]: https://docs.npmjs.com/cli/install

[license]: license

[author]: https://wooorm.com

[contributing]: https://github.com/micromark/.github/blob/HEAD/contributing.md

[support]: https://github.com/micromark/.github/blob/HEAD/support.md

[coc]: https://github.com/micromark/.github/blob/HEAD/code-of-conduct.md

[micromark]: https://github.com/micromark/micromark

[from-markdown]: https://github.com/syntax-tree/mdast-util-from-markdown

[to-markdown]: https://github.com/syntax-tree/mdast-util-to-markdown

[remark]: https://github.com/remarkjs/remark

[mdast]: https://github.com/syntax-tree/mdast

[mdast-util-math]: https://github.com/syntax-tree/mdast-util-math

[katex]: https://katex.org

[katex-options]: https://katex.org/docs/options.html
