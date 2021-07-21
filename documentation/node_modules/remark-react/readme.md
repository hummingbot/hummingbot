# remark-react

[![Build][build-badge]][build]
[![Coverage][coverage-badge]][coverage]
[![Downloads][downloads-badge]][downloads]
[![Chat][chat-badge]][chat]

Transform markdown to React with **[remark][]**, an extensively tested and
pluggable parser.

**Why?**  Using innerHTML and [dangerouslySetInnerHTML][] in [React][] is a
common cause of [XSS][] attacks: user input can include script tags and other
kinds of active content that reaches across domains and harms security.
**remark-react** builds a DOM in React, using [React.createElement][h]: this
means that you can display parsed & formatted Markdown content in an
application without using `dangerouslySetInnerHTML`.

## Installation

[npm][]:

```bash
npm install remark-react
```

## Table of Contents

*   [Usage](#usage)
*   [API](#api)
    *   [remark().use(react\[, options\])](#remarkusereact-options)
*   [Integrations](#integrations)
*   [License](#license)

## Usage

```js
import React from 'react'
import ReactDOM from 'react-dom'
import remark from 'remark'
import remark2react from 'remark-react'

class App extends React.Component {
  constructor() {
    super()
    this.state = { text: '# hello world' }
    this.onChange = this.onChange.bind(this)
  }
  onChange(e) {
    this.setState({ text: e.target.value })
  }
  render() {
    return (
      <div>
        <textarea value={this.state.text} onChange={this.onChange} />
        <div id="preview">
          {
            remark()
              .use(remark2react)
              .processSync(this.state.text).contents
          }
        </div>
      </div>
    )
  }
}

ReactDOM.render(<App />, document.getElementById('root'))
```

## API

### `remark().use(react[, options])`

Transform markdown to React.

##### Options

###### `options.createElement`

How to create elements or components (`Function`).
Default: `require('react').createElement`

###### `options.fragment`

Create fragments instead of an outer `<div>` if available (`Function`).
Default: `require('react').Fragment`

###### `options.sanitize`

Sanitation schema to use (`object` or `boolean`, default: `undefined`).
Passed to [`hast-util-sanitize`][sanitize].
The default schema, if none or `true` is passed, adheres to GitHub’s
sanitation rules.
Setting this to `false` is just as bad as using `dangerouslySetInnerHTML`.

###### `options.prefix`

React key (default: `h-`).

###### `options.remarkReactComponents`

Override default elements, such as `<a>`, `<p>`, etc by defining an object
comprised of `element: Component` key-value pairs (`object`, default:
`undefined`).
For example, to output `<MyLink>` components instead of `<a>`, and
`<MyParagraph>` instead of `<p>`:

```javascript
remarkReactComponents: {
  a: MyLink,
  p: MyParagraph
}
```

###### `options.toHast`

Configure how to transform [mdast][] to [hast][] (`object`, default: `{}`).
Passed to [mdast-util-to-hast][to-hast].

## Integrations

See how to integrate with other remark plugins in the [Integrations][] section
of `remark-html`.

## License

[MIT][license] © [Titus Wormer][author], modified by [Tom MacWright][tom] and
[Mapbox][].

[build-badge]: https://img.shields.io/travis/remarkjs/remark-react.svg

[build]: https://travis-ci.org/remarkjs/remark-react

[coverage-badge]: https://img.shields.io/codecov/c/github/remarkjs/remark-react.svg

[coverage]: https://codecov.io/github/remarkjs/remark-react

[downloads-badge]: https://img.shields.io/npm/dm/remark-react.svg

[downloads]: https://www.npmjs.com/package/remark-react

[chat-badge]: https://img.shields.io/badge/join%20the%20community-on%20spectrum-7b16ff.svg

[chat]: https://spectrum.chat/unified/remark

[npm]: https://docs.npmjs.com/cli/install

[license]: license

[author]: https://wooorm.com

[tom]: https://macwright.org

[mdast]: https://github.com/syntax-tree/mdast

[hast]: https://github.com/syntax-tree/hast

[remark]: https://github.com/remarkjs/remark

[mapbox]: https://www.mapbox.com

[to-hast]: https://github.com/syntax-tree/mdast-util-to-hast#tohastnode-options

[react]: http://facebook.github.io/react/

[dangerouslysetinnerhtml]: https://reactjs.org/docs/dom-elements.html#dangerouslysetinnerhtml

[xss]: https://en.wikipedia.org/wiki/Cross-site_scripting

[h]: https://reactjs.org/docs/react-api.html#createelement

[sanitize]: https://github.com/syntax-tree/hast-util-sanitize

[integrations]: https://github.com/remarkjs/remark-html#integrations
