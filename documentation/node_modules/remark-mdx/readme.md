# remark-mdx

[![Build][build-badge]][build]
[![Downloads][downloads-badge]][downloads]
[![Size][size-badge]][size]
[![Sponsors][sponsors-badge]][collective]
[![Backers][backers-badge]][collective]
[![Chat][chat-badge]][chat]

[**remark**][remark] plugin to support MDX (Markdown 💛 JSX).

This isn’t useful on its own, you’ll probably want to do combine it with other
plugins or do tree traversal yourself to compile to things!

It’s used in [MDXjs][].

## Install

[npm][]:

```sh
npm install remark-mdx
```

## Use

Say we have the following file, `example.md`:

```markdown
# Hello, {data.to}

<Body>
{message}
</Body>

Best, {data.from}
```

And our script, `example.js`, looks as follows:

```js
var vfile = require('to-vfile')
var report = require('vfile-reporter')
var unified = require('unified')
var parse = require('remark-parse')
var stringify = require('remark-stringify')
var mdx = require('remark-mdx')

unified()
  .use(parse, {position: false})
  .use(stringify)
  .use(mdx)
  .use(debug)
  .process(vfile.readSync('example.md'), function (err, file) {
    if (err) throw err
    console.log(String(file))
  })

function debug() {
  return console.dir
}
```

Now, running `node example` yields:

```js
{
  type: 'root',
  children: [
    {
      type: 'heading',
      depth: 1,
      children: [
        {type: 'text', value: 'Hello, '},
        {type: 'mdxSpanExpression', value: 'data.to'}
      ]
    },
    {
      type: 'mdxBlockElement',
      name: 'Body',
      attributes: [],
      children: [{type: 'mdxBlockExpression', value: 'message'}]
    },
    {
      type: 'paragraph',
      children: [
        {type: 'text', value: 'Best, '},
        {type: 'mdxSpanExpression', value: 'data.from'}
      ]
    }
  ]
}
```

```markdown
# Hello, {data.to}

<Body>
  {
    message
  }
</Body>

Best, {data.from}
```

## API

### `remark().use(mdx[, options])`

Plugin to add support for MDX.

## Security

Use of `remark-mdx` does not involve [**rehype**][rehype] ([**hast**][hast]) or
user content so there are no openings for [cross-site scripting (XSS)][xss]
attacks.

## Related

*   [`remark-breaks`](https://github.com/remarkjs/remark-breaks)
    — More breaks
*   [`remark-footnotes`](https://github.com/remarkjs/remark-footnotes)
    — Footnotes support
*   [`remark-frontmatter`](https://github.com/remarkjs/remark-frontmatter)
    — Frontmatter (yaml, toml, and more) support
*   [`remark-github`](https://github.com/remarkjs/remark-github)
    — References to issues, PRs, comments, users, etc
*   [`remark-math`](https://github.com/rokt33r/remark-math)
    — Inline and block math

## Contribute

See the [Support][] and [Contributing][] guidelines on the MDX website for ways
to (get) help.

This project has a [code of conduct][coc].
By interacting with this repository, organization, or community you agree to
abide by its terms.

## License

[MIT][license] © [Titus Wormer][author]

[build-badge]: https://img.shields.io/travis/mdx-js/mdx/master.svg

[build]: https://travis-ci.org/mdx-js/mdx

[downloads-badge]: https://img.shields.io/npm/dm/remark-mdx.svg

[downloads]: https://www.npmjs.com/package/remark-mdx

[size-badge]: https://img.shields.io/bundlephobia/minzip/remark-mdx.svg

[size]: https://bundlephobia.com/result?p=remark-mdx

[sponsors-badge]: https://opencollective.com/unified/sponsors/badge.svg

[backers-badge]: https://opencollective.com/unified/backers/badge.svg

[collective]: https://opencollective.com/unified

[chat-badge]: https://img.shields.io/badge/chat-spectrum-7b16ff.svg

[chat]: https://spectrum.chat/unified/remark

[npm]: https://docs.npmjs.com/cli/install

[contributing]: https://mdxjs.com/contributing

[support]: https://mdxjs.com/support

[coc]: https://github.com/mdx-js/.github/blob/master/code-of-conduct.md

[license]: license

[author]: https://wooorm.com

[remark]: https://github.com/remarkjs/remark

[xss]: https://en.wikipedia.org/wiki/Cross-site_scripting

[rehype]: https://github.com/rehypejs/rehype

[hast]: https://github.com/syntax-tree/hast

[mdxjs]: https://mdxjs.com
