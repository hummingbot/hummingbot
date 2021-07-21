# rehype-react

[![Build Status][travis-badge]][travis-status]

Compiles [HAST][] to [React][] with [**rehype**][rehype].

## Install

[npm][]:

```bash
npm install rehype-react
```

## Use

The following example shows how to create a markdown input textarea,
and corresponding rendered HTML output.  The markdown is processed
to add a Table of Contents and to render GitHub mentions (and other
cool GH features), and to highlight code blocks.

```js
var React = require('react');
var ReactDOM = require('react-dom');
var unified = require('unified');
var markdown = require('remark-parse');
var toc = require('remark-toc');
var github = require('remark-github');
var remark2rehype = require('remark-rehype');
var highlight = require('rehype-highlight');
var rehype2react = require('rehype-react');

var processor = unified()
  .use(markdown)
  .use(toc)
  .use(github, {
    repository: 'https://github.com/rhysd/rehype-react'
  })
  .use(remark2rehype)
  .use(highlight)
  .use(rehype2react, {
    createElement: React.createElement
  });

var App = React.createClass({
  getInitialState() {
    return {text: '# Hello\n\n## Table of Contents\n\n## @rhysd'};
  },
  onChange(ev) {
    this.setState({text: ev.target.value});
  },
  render() {
    return (<div>
      <textarea
        value={this.state.text}
        onChange={this.onChange} />
      <div id='preview'>
        {processor.processSync(this.state.text).contents}
      </div>
    </div>);
  }
});

ReactDOM.render(<App />, document.getElementById('app'));
```

Yields (in `id="preview"`, on first render):

```html
<div><h1 id="hello">Hello</h1>
<h2 id="table-of-contents">Table of Contents</h2>
<ul>
<li><a href="#rhysd">@rhysd</a></li>
</ul>
<h2 id="rhysd"><a href="https://github.com/rhysd"><strong>@rhysd</strong></a></h2></div>
```

## Programmatic

### `origin.use(rehype2react[, options])`

Normally, the `use`d on processor compiles to a string, but this
compiler generates a `ReactElement` instead.  It’s accessible
through `file.contents`.

###### `options`

*   `createElement` (`Function`, required)
    — Function to use to create `ReactElement`s;
*   `components` (`Object`, default: `{}`)
    — Register components;
*   `prefix` (`string`, default: `'h-'`)
    — Prefix for key to use on generated `ReactElement`s.

## License

[MIT](LICENSE) © [Titus Wormer][titus], modified by
[Tom MacWright][tom] and [Mapbox][] and [rhysd][].

[titus]: http://wooorm.com

[tom]: http://www.macwright.org/

[mapbox]: https://www.mapbox.com/

[rhysd]: https://rhysd.github.io

[travis-badge]: https://travis-ci.org/rhysd/rehype-react.svg?branch=master

[travis-status]: https://travis-ci.org/rhysd/rehype-react

[npm]: https://docs.npmjs.com/cli/install

[hast]: https://github.com/wooorm/hast

[react]: https://github.com/facebook/react

[rehype]: https://github.com/wooorm/rehype
