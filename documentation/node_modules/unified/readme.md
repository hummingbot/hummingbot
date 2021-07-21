# [![unified][logo]][site]

[![GitHub CI][github-ci-badge]][github-ci]
[![Build][build-badge]][build]
[![Coverage][coverage-badge]][coverage]
[![Downloads][downloads-badge]][downloads]
[![Size][size-badge]][size]
[![Sponsors][sponsors-badge]][collective]
[![Backers][backers-badge]][collective]
[![Chat][chat-badge]][chat]

**unified** is an interface for processing text using syntax trees.
It’s what powers [**remark**][remark], [**retext**][retext], and
[**rehype**][rehype], and allows for processing between formats.

## Intro

**unified** enables new exciting projects like [Gatsby][] to pull in Markdown,
[MDX][] to embed [JSX][], and [Prettier][] to format it.
It’s used in about 300k projects on GitHub and has about 10m downloads each
month on npm: you’re probably using it.
Some notable users are [Node.js][], [ZEIT][],  [Netlify][], [GitHub][],
[Mozilla][], [WordPress][], [Adobe][], [Facebook][], [Google][], and many more.

*   To read about what we are up to, follow us on [Medium][] and [Twitter][]
*   For a less technical and more practical introduction to unified, visit
    [`unifiedjs.com`][site] and try its introductory [Guides][]
*   Browse [awesome unified][awesome] to find out more about the ecosystem
*   Questions?
    Get help on [our Spectrum community][spectrum]!
*   Check out [Contribute][] below to find out how to help out, or become a
    backer or sponsor on [Open Collective][collective]

## Sponsors

<!--lint ignore no-html maximum-line-length-->

<table>
  <tr valign="top">
    <td width="20%" align="center">
      <a href="https://zeit.co"><img src="https://avatars1.githubusercontent.com/u/14985020?s=400&v=4"></a>
      <br><br>🥇
      <a href="https://zeit.co">ZEIT</a>
    </td>
    <td width="20%" align="center">
      <a href="https://www.gatsbyjs.org"><img src="https://avatars1.githubusercontent.com/u/12551863?s=400&v=4"></a>
      <br><br>🥇
      <a href="https://www.gatsbyjs.org">Gatsby</a></td>
    <td width="20%" align="center">
      <a href="https://www.netlify.com"><img src="https://avatars1.githubusercontent.com/u/7892489?s=400&v=4"></a>
      <br><br>🥇
      <a href="https://www.netlify.com">Netlify</a>
    </td>
    <td width="20%" align="center">
      <a href="https://www.holloway.com"><img src="https://avatars1.githubusercontent.com/u/35904294?s=400&v=4"></a>
      <br><br>
      <a href="https://www.holloway.com">Holloway</a>
    </td>
    <td width="20%" align="center">
      <br><br><br><br>
      <a href="https://opencollective.com/unified"><strong>You?</strong>
    </td>
  </tr>
</table>

[**Read more about the unified collective on Medium »**][announcement]

## Install

[npm][]:

```sh
npm install unified
```

This package comes with types.
If you’re using TypeScript, make sure to also install [`@types/unist`][ts-unist]
and [`@types/vfile`][ts-vfile].

## Use

```js
var unified = require('unified')
var markdown = require('remark-parse')
var remark2rehype = require('remark-rehype')
var doc = require('rehype-document')
var format = require('rehype-format')
var html = require('rehype-stringify')
var report = require('vfile-reporter')

unified()
  .use(markdown)
  .use(remark2rehype)
  .use(doc, {title: '👋🌍'})
  .use(format)
  .use(html)
  .process('# Hello world!', function(err, file) {
    console.error(report(err || file))
    console.log(String(file))
  })
```

Yields:

```txt
no issues found
```

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>👋🌍</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
  </head>
  <body>
    <h1>Hello world!</h1>
  </body>
</html>
```

## Table of Contents

*   [Description](#description)
*   [API](#api)
    *   [`processor()`](#processor)
    *   [`processor.use(plugin[, options])`](#processoruseplugin-options)
    *   [`processor.parse(file)`](#processorparsefile)
    *   [`processor.stringify(node[, file])`](#processorstringifynode-file)
    *   [`processor.run(node[, file][, done])`](#processorrunnode-file-done)
    *   [`processor.runSync(node[, file])`](#processorrunsyncnode-file)
    *   [`processor.process(file[, done])`](#processorprocessfile-done)
    *   [`processor.processSync(file|value)`](#processorprocesssyncfilevalue)
    *   [`processor.data([key[, value]])`](#processordatakey-value)
    *   [`processor.freeze()`](#processorfreeze)
*   [`Plugin`](#plugin)
    *   [`function attacher([options])`](#function-attacheroptions)
    *   [`function transformer(node, file[, next])`](#function-transformernode-file-next)
*   [`Preset`](#preset)
*   [Contribute](#contribute)
*   [Acknowledgments](#acknowledgments)
*   [License](#license)

## Description

**unified** is an interface for processing text using syntax trees.
Syntax trees are a representation understandable to programs.
Those programs, called [*plugin*][plugin]s, take these trees and inspect and
modify them.
To get to the syntax tree from text, there is a [*parser*][parser].
To get from that back to text, there is a [*compiler*][compiler].
This is the [*process*][process] of a *processor*.

```ascii
| ........................ process ........................... |
| .......... parse ... | ... run ... | ... stringify ..........|

          +--------+                     +----------+
Input ->- | Parser | ->- Syntax Tree ->- | Compiler | ->- Output
          +--------+          |          +----------+
                              X
                              |
                       +--------------+
                       | Transformers |
                       +--------------+
```

###### Processors

Every **processor** implements another processor.
To create a processor, call another processor.
The new processor is configured to work the same as its ancestor.
But when the descendant processor is configured in the future it does not affect
the ancestral processor.

When processors are exposed from a module (for example, `unified` itself) they
should not be configured directly, as that would change their behaviour for all
module users.
Those processors are [*frozen*][freeze] and they should be called to create a
new processor before they are used.

###### Syntax trees

The **syntax trees** used in **unified** are [**unist**][unist] nodes.
A [**node**][node] is a plain JavaScript objects with a `type` field.
The semantics of nodes and format of syntax trees is defined by other projects.

There are several [*utilities*][unist-utilities] for working with nodes.

*   [**hast**][hast] — HTML
*   [**mdast**][mdast] — Markdown
*   [**nlcst**][nlcst] — Natural language

###### List of Processors

The following projects process different [*syntax tree*][syntax-tree] formats.
They parse text to a syntax tree and compile that back to text.
These processors can be used as is, or their parser and stringifier can be mixed
and matched with **unified** and plugins to process between different syntaxes.

*   [**rehype**][rehype] ([*hast*][hast]) — HTML
*   [**remark**][remark] ([*mdast*][mdast]) — Markdown
*   [**retext**][retext] ([*nlcst*][nlcst]) — Natural language

###### List of Plugins

The below [**plugins**][plugin] work with **unified**, on all [*syntax
tree*][syntax-tree] formats:

*   [`unified-diff`](https://github.com/unifiedjs/unified-diff)
    — Ignore messages for unchanged lines in Travis

See [**remark**][remark-plugins], [**rehype**][rehype-plugins], and
[**retext**][retext-plugins] for their lists of plugins.

###### File

When processing a document, **metadata** is often gathered about that document.
[**vfile**][vfile] is a virtual file format that stores data, metadata, and
messages about files for **unified** and its plugins.

There are several [*utilities*][vfile-utilities] for working with these files.

###### Configuration

[*Processors*][processors] are configured with [*plugin*][plugin]s or
with the [`data`][data] method.

###### Integrations

**unified** can integrate with the file system with [`unified-engine`][engine].
CLI apps can be created with [`unified-args`][args], Gulp plugins with
[`unified-engine-gulp`][gulp], and Atom Linters with
[`unified-engine-atom`][atom].

[`unified-stream`][stream] provides a streaming interface.

###### Programming interface

The API provided by **unified** allows multiple files to be processed and gives
access to *metadata* (such as lint messages):

```js
var unified = require('unified')
var markdown = require('remark-parse')
var styleGuide = require('remark-preset-lint-markdown-style-guide')
var remark2retext = require('remark-retext')
var english = require('retext-english')
var equality = require('retext-equality')
var remark2rehype = require('remark-rehype')
var html = require('rehype-stringify')
var report = require('vfile-reporter')

unified()
  .use(markdown)
  .use(styleGuide)
  .use(
    remark2retext,
    unified()
      .use(english)
      .use(equality)
  )
  .use(remark2rehype)
  .use(html)
  .process('*Emphasis* and _stress_, you guys!', function(err, file) {
    console.error(report(err || file))
    console.log(String(file))
  })
```

Yields:

```txt
  1:16-1:24  warning  Emphasis should use `*` as a marker                                  emphasis-marker  remark-lint
  1:30-1:34  warning  `guys` may be insensitive, use `people`, `persons`, `folks` instead  gals-men         retext-equality

⚠ 2 warnings
```

```html
<p><em>Emphasis</em> and <em>stress</em>, you guys!</p>
```

###### Processing between syntaxes

[*Processors*][processors] can be combined in two modes.

**Bridge** mode transforms the [*syntax tree*][syntax-tree] from one format
(*origin*) to another (*destination*).
Another processor runs on the destination tree.
Finally, the original processor continues transforming the origin tree.

**Mutate** mode also transforms the syntax tree from one format to another.
But the original processor continues transforming the destination tree.

In the previous example (“Programming interface”), `remark-retext` is used in
*bridge* mode: the origin syntax tree is kept after [**retext**][retext] is
done; whereas `remark-rehype` is used in *mutate* mode: it sets a new syntax
tree and discards the origin tree.

*   [`remark-retext`][remark-retext]
*   [`remark-rehype`][remark-rehype]
*   [`rehype-retext`][rehype-retext]
*   [`rehype-remark`][rehype-remark]

## API

### `processor()`

[*Processor*][processors] describing how to *process* text.

###### Returns

`Function` — New [*unfrozen*][freeze] processor that is configured to work the
same as its ancestor.
When the descendant processor is configured in the future it does not affect the
ancestral processor.

###### Example

The following example shows how a new processor can be created (from the remark
processor) and linked to **stdin**(4) and **stdout**(4).

```js
var remark = require('remark')
var concat = require('concat-stream')

process.stdin.pipe(concat(onconcat))

function onconcat(buf) {
  var doc = remark()
    .processSync(buf)
    .toString()

  process.stdout.write(doc)
}
```

### `processor.use(plugin[, options])`

[*Configure*][configuration] the processor to use a [*plugin*][plugin] and
optionally configure that plugin with options.

###### Signatures

*   `processor.use(plugin[, options])`
*   `processor.use(preset)`
*   `processor.use(list)`

###### Parameters

*   `plugin` ([`Attacher`][plugin])
*   `options` (`*`, optional) — Configuration for `plugin`
*   `preset` (`Object`) — Object with an optional `plugins` (set to `list`),
    and/or an optional `settings` object
*   `list` (`Array`) — List of plugins, presets, and pairs (`plugin` and
    `options` in an array)

###### Returns

`processor` — The processor that `use` was called on.

###### Note

`use` cannot be called on [*frozen*][freeze] processors.
Call the processor first to create a new unfrozen processor.

###### Example

There are many ways to pass plugins to `.use()`.
The below example gives an overview.

```js
var unified = require('unified')

unified()
  // Plugin with options:
  .use(plugin, {})
  // Plugins:
  .use([plugin, pluginB])
  // Two plugins, the second with options:
  .use([plugin, [pluginB, {}]])
  // Preset with plugins and settings:
  .use({plugins: [plugin, [pluginB, {}]], settings: {position: false}})
  // Settings only:
  .use({settings: {position: false}})

function plugin() {}
function pluginB() {}
```

### `processor.parse(file)`

Parse text to a [*syntax tree*][syntax-tree].

###### Parameters

*   `file` ([`VFile`][vfile]) — [*File*][file], any value accepted by `vfile()`

###### Returns

[`Node`][node] — Parsed [*syntax tree*][syntax-tree] representing `file`.

###### Note

`parse` freezes the processor if not already [*frozen*][freeze].

`parse` performs the [*parse phase*][description], not the *run phase* or other
phases.

###### Example

The below example shows how `parse` can be used to create a syntax tree from a
file.

```js
var unified = require('unified')
var markdown = require('remark-parse')

var tree = unified()
  .use(markdown)
  .parse('# Hello world!')

console.log(tree)
```

Yields:

```js
{ type: 'root',
  children:
   [ { type: 'heading',
       depth: 1,
       children: [Array],
       position: [Position] } ],
  position:
   { start: { line: 1, column: 1, offset: 0 },
     end: { line: 1, column: 15, offset: 14 } } }
```

#### `processor.Parser`

A **parser** handles the parsing of text to a [*syntax tree*][syntax-tree].
Used in the [*parse phase*][description] and called with a `string` and
[`VFile`][vfile] representation of the text to parse.

`Parser` can be a function, in which case it must return a [`Node`][node]: the
syntax tree representation of the given file.

`Parser` can also be a constructor function (a function with a `parse` field, or
other fields, in its `prototype`), in which case it’s constructed with `new`.
Instances must have a `parse` method that is called without arguments and must
return a [`Node`][node].

### `processor.stringify(node[, file])`

Stringify a [*syntax tree*][syntax-tree] to text.

###### Parameters

*   `node` ([`Node`][node]) — [*Syntax tree*][syntax-tree] to stringify
*   `file` ([`VFile`][vfile], optional) — [*File*][file], any value accepted by
    `vfile()`

###### Returns

`string` (see notes) — Textual representation of the [*syntax
tree*][syntax-tree]

###### Note

`stringify` freezes the processor if not already [*frozen*][freeze].

`stringify` performs the [*stringify phase*][description], not the *run phase*
or other phases.

Be aware that [*compiler*][compiler]s typically, but not always, return
`string`.
Some compilers, such as the one configured with [`rehype-react`][rehype-react],
return other values (in this case, a React tree).
When using TypeScript, cast the type on your side.

###### Example

The below example shows how `stringify` can be used to stringify a syntax tree.

```js
var unified = require('unified')
var html = require('rehype-stringify')
var h = require('hastscript')

var tree = h('h1', 'Hello world!')

var doc = unified()
  .use(html)
  .stringify(tree)

console.log(doc)
```

Yields:

```html
<h1>Hello world!</h1>
```

#### `processor.Compiler`

A **compiler** handles the compiling of a [*syntax tree*][syntax-tree] to text.
Used in the [*stringify phase*][description] and called with a [`Node`][node]
and [`VFile`][file] representation of syntax tree to compile.

`Compiler` can be a function, in which case it should return a `string`: the
textual representation of the syntax tree.

`Compiler` can also be a constructor function (a function with a `compile`
field, or other fields, in its `prototype`), in which case it’s constructed with
`new`.
Instances must have a `compile` method that is called without arguments and
should return a `string`.

### `processor.run(node[, file][, done])`

Run [*transformers*][transformer] on a [*syntax tree*][syntax-tree].

###### Parameters

*   `node` ([`Node`][node]) — [*Syntax tree*][syntax-tree] to run on
*   `file` ([`VFile`][vfile], optional) — [*File*][file], any value accepted by
    `vfile()`
*   `done` ([`Function`][run-done], optional) — Callback

###### Returns

[`Promise`][promise] if `done` is not given.
The returned promise is rejected with a fatal error, or resolved with the
transformed [*syntax tree*][syntax-tree].

###### Note

`run` freezes the processor if not already [*frozen*][freeze].

`run` performs the [*run phase*][description], not other phases.

#### `function done(err[, node, file])`

Callback called when [*transformers*][transformer] are done.
Called with either an error or results.

###### Parameters

*   `err` (`Error`, optional) — Fatal error
*   `node` ([`Node`][node], optional) — Transformed [*syntax tree*][syntax-tree]
*   `file` ([`VFile`][vfile], optional) — [*File*][file]

###### Example

The below example shows how `run` can be used to transform a syntax tree.

```js
var unified = require('unified')
var references = require('remark-reference-links')
var u = require('unist-builder')

var tree = u('root', [
  u('paragraph', [
    u('link', {href: 'https://example.com'}, [u('text', 'Example Domain')])
  ])
])

unified()
  .use(references)
  .run(tree, function(err, tree) {
    if (err) throw err
    console.log(tree)
  })
```

Yields:

```js
{ type: 'root',
  children:
   [ { type: 'paragraph', children: [Array] },
     { type: 'definition',
       identifier: '1',
       title: undefined,
       url: undefined } ] }
```

### `processor.runSync(node[, file])`

Run [*transformers*][transformer] on a [*syntax tree*][syntax-tree].

An error is thrown if asynchronous [*plugin*][plugin]s are configured.

###### Parameters

*   `node` ([`Node`][node]) — [*Syntax tree*][syntax-tree] to run on
*   `file` ([`VFile`][vfile], optional) — [*File*][file], any value accepted by
    `vfile()`

###### Returns

[`Node`][node] — Transformed [*syntax tree*][syntax-tree].

###### Note

`runSync` freezes the processor if not already [*frozen*][freeze].

`runSync` performs the [*run phase*][description], not other phases.

### `processor.process(file[, done])`

[*Process*][description] the given [*file*][file] as configured on the
processor.

###### Parameters

*   `file` ([`VFile`][vfile]) — [*File*][file], any value accepted by `vfile()`
*   `done` ([`Function`][process-done], optional) — Callback

###### Returns

[`Promise`][promise] if `done` is not given.
The returned promise is rejected with a fatal error, or resolved with the
processed [*file*][file].

The parsed, transformed, and stringified value is exposed on
[`file.contents`][vfile-contents].

###### Note

`process` freezes the processor if not already [*frozen*][freeze].

`process` performs the [*parse*, *run*, and *stringify* phases][description].

Be aware that [*compiler*][compiler]s typically, but not always, return
`string`.
Some compilers, such as the one configured with [`rehype-react`][rehype-react],
return other values (in this case, a React tree).
When using TypeScript, cast the type of [`file.contents`][vfile-contents] on
your side.

###### Example

The below example shows how `process` can be used to process a file, whether
transformers are asynchronous or not, with promises.

```js
var unified = require('unified')
var markdown = require('remark-parse')
var remark2rehype = require('remark-rehype')
var doc = require('rehype-document')
var format = require('rehype-format')
var html = require('rehype-stringify')

unified()
  .use(markdown)
  .use(remark2rehype)
  .use(doc, {title: '👋🌍'})
  .use(format)
  .use(html)
  .process('# Hello world!')
  .then(
    function(file) {
      console.log(String(file))
    },
    function(err) {
      console.error(String(err))
    }
  )
```

Yields:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>👋🌍</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
  </head>
  <body>
    <h1>Hello world!</h1>
  </body>
</html>
```

#### `function done(err, file)`

Callback called when the [*process*][description] is done.
Called with a fatal error, if any, and a [*file*][file].

###### Parameters

*   `err` (`Error`, optional) — Fatal error
*   `file` ([`VFile`][vfile]) — Processed [*file*][file]

###### Example

The below example shows how `process` can be used to process a file, whether
transformers are asynchronous or not, with a callback.

```js
var unified = require('unified')
var parse = require('remark-parse')
var stringify = require('remark-stringify')
var github = require('remark-github')
var report = require('vfile-reporter')

unified()
  .use(parse)
  .use(github)
  .use(stringify)
  .process('@wooorm', function(err, file) {
    console.error(report(err || file))
    console.log(String(file))
  })
```

Yields:

```txt
no issues found
```

```markdown
[**@wooorm**](https://github.com/wooorm)
```

### `processor.processSync(file|value)`

[*Process*][description] the given [*file*][file] as configured on the
processor.

An error is thrown if asynchronous [*plugin*][plugin]s are configured.

###### Parameters

*   `file` ([`VFile`][vfile]) — [*File*][file], any value accepted by `vfile()`

###### Returns

([`VFile`][vfile]) — Processed [*file*][file]

###### Note

`processSync` freezes the processor if not already [*frozen*][freeze].

`processSync` performs the [*parse*, *run*, and *stringify*
phases][description].

Be aware that [*compiler*][compiler]s typically, but not always, return
`string`.
Some compilers, such as the one configured with [`rehype-react`][rehype-react],
return other values (in this case, a React tree).
When using TypeScript, cast the type of [`file.contents`][vfile-contents] on
your side.

###### Example

The below example shows how `processSync` can be used to process a file, if all
transformers are synchronous.

```js
var unified = require('unified')
var markdown = require('remark-parse')
var remark2rehype = require('remark-rehype')
var doc = require('rehype-document')
var format = require('rehype-format')
var html = require('rehype-stringify')

var processor = unified()
  .use(markdown)
  .use(remark2rehype)
  .use(doc, {title: '👋🌍'})
  .use(format)
  .use(html)

console.log(processor.processSync('# Hello world!').toString())
```

Yields:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>👋🌍</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
  </head>
  <body>
    <h1>Hello world!</h1>
  </body>
</html>
```

### `processor.data([key[, value]])`

[*Configure*][configuration] the processor with information available to all
[*plugin*][plugin]s.
Information is stored in an in-memory key-value store.

Typically, options can be given to a specific plugin, but sometimes it makes
sense to have information shared with several plugins.
For example, a list of HTML elements that are self-closing, which is needed
during all [*phases*][description] of the *process*.

###### Signatures

*   `processor = processor.data(key, value)`
*   `processor = processor.data(values)`
*   `value = processor.data(key)`
*   `info = processor.data()`

###### Parameters

*   `key` (`string`, optional) — Identifier
*   `value` (`*`, optional) — Value to set
*   `values` (`Object`, optional) — Values to set

###### Returns

*   `processor` — If setting, the processor that `data` is called on
*   `value` (`*`) — If getting, the value at `key`
*   `info` (`Object`) — Without arguments, the key-value store

###### Note

Setting information cannot occur on [*frozen*][freeze] processors.
Call the processor first to create a new unfrozen processor.

###### Example

The following example show how to get and set information:

```js
var unified = require('unified')

var processor = unified().data('alpha', 'bravo')

processor.data('alpha') // => 'bravo'

processor.data() // {alpha: 'bravo'}

processor.data({charlie: 'delta'})

processor.data() // {charlie: 'delta'}
```

### `processor.freeze()`

**Freeze** a processor.
*Frozen* processors are meant to be extended and not to be configured directly.

Once a processor is frozen it cannot be *unfrozen*.
New processors working the same way can be created by calling the processor.

It’s possible to freeze processors explicitly by calling `.freeze()`.
Processors freeze implicitly when [`.parse()`][parse], [`.run()`][run],
[`.runSync()`][run-sync], [`.stringify()`][stringify], [`.process()`][process],
or [`.processSync()`][process-sync] are called.

###### Returns

`processor` — The processor that `freeze` was called on.

###### Example

The following example, `index.js`, shows how rehype prevents extensions to
itself:

```js
var unified = require('unified')
var parse = require('rehype-parse')
var stringify = require('rehype-stringify')

module.exports = unified()
  .use(parse)
  .use(stringify)
  .freeze()
```

The below example, `a.js`, shows how that processor can be used and configured.

```js
var rehype = require('rehype')
var format = require('rehype-format')
// …

rehype()
  .use(format)
  // …
```

The below example, `b.js`, shows a similar looking example that operates on the
frozen rehype interface because it does not call `rehype`.
If this behaviour was allowed it would result in unexpected behaviour so an
error is thrown.
**This is invalid**:

```js
var rehype = require('rehype')
var format = require('rehype-format')
// …

rehype
  .use(format)
  // …
```

Yields:

```txt
~/node_modules/unified/index.js:440
    throw new Error(
    ^

Error: Cannot invoke `use` on a frozen processor.
Create a new processor first, by invoking it: use `processor()` instead of `processor`.
    at assertUnfrozen (~/node_modules/unified/index.js:440:11)
    at Function.use (~/node_modules/unified/index.js:172:5)
    at Object.<anonymous> (~/b.js:6:4)
```

## `Plugin`

**Plugins** [*configure*][configuration] the processors they are applied on in
the following ways:

*   They change the processor: such as the [*parser*][parser], the
    [*compiler*][compiler], or configuring [*data*][data]
*   They specify how to handle [*syntax trees*][syntax-tree] and [*files*][file]

Plugins are a concept.
They materialise as [`attacher`][attacher]s.

###### Example

`move.js`:

```js
module.exports = move

function move(options) {
  var expected = (options || {}).extname

  if (!expected) {
    throw new Error('Missing `extname` in options')
  }

  return transformer

  function transformer(tree, file) {
    if (file.extname && file.extname !== expected) {
      file.extname = expected
    }
  }
}
```

`index.md`:

```markdown
# Hello, World!
```

`index.js`:

```js
var unified = require('unified')
var parse = require('remark-parse')
var remark2rehype = require('remark-rehype')
var stringify = require('rehype-stringify')
var vfile = require('to-vfile')
var report = require('vfile-reporter')
var move = require('./move')

unified()
  .use(parse)
  .use(remark2rehype)
  .use(move, {extname: '.html'})
  .use(stringify)
  .process(vfile.readSync('index.md'), function(err, file) {
    console.error(report(err || file))
    if (file) {
      vfile.writeSync(file) // Written to `index.html`.
    }
  })
```

Yields:

```txt
index.md: no issues found
```

`index.html`:

```html
<h1>Hello, World!</h1>
```

### `function attacher([options])`

**Attachers** are materialised [*plugin*][plugin]s.
An attacher is a function that can receive options and
[*configures*][configuration] the processor.

Attachers change the processor, such as the [*parser*][parser], the
[*compiler*][compiler], configuring [*data*][data], or by specifying how the
[*syntax tree*][syntax-tree] or [*file*][file] are handled.

###### Context

The context object (`this`) is set to the processor the attacher is applied on.

###### Parameters

*   `options` (`*`, optional) — Configuration

###### Returns

[`transformer`][transformer] — Optional.

###### Note

Attachers are called when the processor is [*frozen*][freeze], not when they are
applied.

### `function transformer(node, file[, next])`

**Transformers** handle [*syntax tree*][syntax-tree]s and [*file*][file]s.
A transformer is a function that is called each time a syntax tree and file are
passed through the [*run phase*][description].
If an error occurs (either because it’s thrown, returned, rejected, or passed to
[`next`][next]), the process stops.

The *run phase* is handled by [`trough`][trough], see its documentation for the
exact semantics of these functions.

###### Parameters

*   `node` ([`Node`][node]) — [*Syntax tree*][syntax-tree] to handle
*   `file` ([`VFile`][vfile]) — [*File*][file] to handle
*   `next` ([`Function`][next], optional)

###### Returns

*   `void` — If nothing is returned, the next transformer keeps using same tree.
*   `Error` — Fatal error to stop the process
*   `node` ([`Node`][node]) — New [*syntax tree*][syntax-tree].
    If returned, the next transformer is given this new tree
*   `Promise` — Returned to perform an asynchronous operation.
    The promise **must** be resolved (optionally with a [`Node`][node]) or
    rejected (optionally with an `Error`)

#### `function next(err[, tree[, file]])`

If the signature of a [*transformer*][transformer] includes `next` (the third
argument), the transformer **may** perform asynchronous operations, and **must**
call `next()`.

###### Parameters

*   `err` (`Error`, optional) — Fatal error to stop the process
*   `node` ([`Node`][node], optional) — New [*syntax tree*][syntax-tree].
    If given, the next transformer is given this new tree
*   `file` ([`VFile`][vfile], optional) — New [*file*][file].
    If given, the next transformer is given this new file

## `Preset`

**Presets** are sharable [*configuration*][configuration].
They can contain [*plugins*][plugin] and settings.

###### Example

`preset.js`:

```js
exports.settings = {bullet: '*', emphasis: '*', fences: true}

exports.plugins = [
  require('remark-preset-lint-recommended'),
  require('remark-preset-lint-consistent'),
  require('remark-comment-config'),
  [require('remark-toc'), {maxDepth: 3, tight: true}],
  require('remark-license')
]
```

`readme.md`:

```markdown
# Hello, World!

_Emphasis_ and **importance**.

## Table of Contents

## API

## License
```

`index.js`:

```js
var remark = require('remark')
var vfile = require('to-vfile')
var report = require('vfile-reporter')
var preset = require('./preset')

remark()
  .use(preset)
  .process(vfile.readSync('readme.md'), function(err, file) {
    console.error(report(err || file))

    if (file) {
      vfile.writeSync(file)
    }
  })
```

Yields:

```txt
readme.md: no issues found
```

`readme.md` now contains:

```markdown
# Hello, World!

*Emphasis* and **importance**.

## Table of Contents

*   [API](#api)
*   [License](#license)

## API

## License

[MIT](license) © [Titus Wormer](https://wooorm.com)
```

## Contribute

See [`contributing.md`][contributing] in [`unifiedjs/.github`][health] for ways
to get started.
See [`support.md`][support] for ways to get help.
Ideas for new plugins and tools can be posted in [`unifiedjs/ideas`][ideas].

A curated list of awesome unified resources can be found in [**awesome
unified**][awesome].

This project has a [Code of Conduct][coc].
By interacting with this repository, organisation, or community you agree to
abide by its terms.

## Acknowledgments

Preliminary work for unified was done [in 2014][preliminary] for
[**retext**][retext] and inspired by [`ware`][ware].
Further incubation happened in [**remark**][remark].
The project was finally [externalised][] in 2015 and [published][] as `unified`.
The project was authored by [**@wooorm**](https://github.com/wooorm).

Although `unified` since moved its plugin architecture to [`trough`][trough],
thanks to [**@calvinfo**](https://github.com/calvinfo),
[**@ianstormtaylor**](https://github.com/ianstormtaylor), and others for their
work on [`ware`][ware], as it was a huge initial inspiration.

## License

[MIT][license] © [Titus Wormer][author]

<!-- Definitions -->

[logo]: https://raw.githubusercontent.com/unifiedjs/unified/39917ea/logo.svg?sanitize=true

[github-ci-badge]: https://github.com/unifiedjs/unified/workflows/CI/badge.svg

[github-ci]: https://github.com/unifiedjs/unified/actions

[build-badge]: https://img.shields.io/travis/unifiedjs/unified.svg

[build]: https://travis-ci.org/unifiedjs/unified

[coverage-badge]: https://img.shields.io/codecov/c/github/unifiedjs/unified.svg

[coverage]: https://codecov.io/github/unifiedjs/unified

[downloads-badge]: https://img.shields.io/npm/dm/unified.svg

[downloads]: https://www.npmjs.com/package/unified

[size-badge]: https://img.shields.io/bundlephobia/minzip/unified.svg

[size]: https://bundlephobia.com/result?p=unified

[sponsors-badge]: https://opencollective.com/unified/sponsors/badge.svg

[backers-badge]: https://opencollective.com/unified/backers/badge.svg

[collective]: https://opencollective.com/unified

[chat-badge]: https://img.shields.io/badge/chat-spectrum-7b16ff.svg

[chat]: https://spectrum.chat/unified

[health]: https://github.com/unifiedjs/.github

[contributing]: https://github.com/unifiedjs/.github/blob/master/contributing.md

[support]: https://github.com/unifiedjs/.github/blob/master/support.md

[coc]: https://github.com/unifiedjs/.github/blob/master/code-of-conduct.md

[awesome]: https://github.com/unifiedjs/awesome-unified

[license]: license

[author]: https://wooorm.com

[npm]: https://docs.npmjs.com/cli/install

[ts-unist]: https://www.npmjs.com/package/@types/unist

[ts-vfile]: https://www.npmjs.com/package/@types/vfile

[site]: https://unifiedjs.com

[medium]: https://medium.com/unifiedjs

[announcement]: https://medium.com/unifiedjs/collectively-evolving-through-crowdsourcing-22c359ea95cc

[twitter]: https://twitter.com/unifiedjs

[guides]: https://unifiedjs.com/#guides

[spectrum]: https://spectrum.chat/unified

[rehype]: https://github.com/rehypejs/rehype

[remark]: https://github.com/remarkjs/remark

[retext]: https://github.com/retextjs/retext

[hast]: https://github.com/syntax-tree/hast

[mdast]: https://github.com/syntax-tree/mdast

[nlcst]: https://github.com/syntax-tree/nlcst

[unist]: https://github.com/syntax-tree/unist

[engine]: https://github.com/unifiedjs/unified-engine

[args]: https://github.com/unifiedjs/unified-args

[gulp]: https://github.com/unifiedjs/unified-engine-gulp

[atom]: https://github.com/unifiedjs/unified-engine-atom

[remark-rehype]: https://github.com/remarkjs/remark-rehype

[remark-retext]: https://github.com/remarkjs/remark-retext

[rehype-retext]: https://github.com/rehypejs/rehype-retext

[rehype-remark]: https://github.com/rehypejs/rehype-remark

[unist-utilities]: https://github.com/syntax-tree/unist#list-of-utilities

[vfile]: https://github.com/vfile/vfile

[vfile-contents]: https://github.com/vfile/vfile#vfilecontents

[vfile-utilities]: https://github.com/vfile/vfile#related-tools

[node]: https://github.com/syntax-tree/unist#node

[description]: #description

[syntax-tree]: #syntax-trees

[configuration]: #configuration

[file]: #file

[processors]: #processors

[process]: #processorprocessfile-done

[process-sync]: #processorprocesssyncfilevalue

[parse]: #processorparsefile

[parser]: #processorparser

[stringify]: #processorstringifynode-file

[run]: #processorrunnode-file-done

[run-sync]: #processorrunsyncnode-file

[compiler]: #processorcompiler

[data]: #processordatakey-value

[attacher]: #function-attacheroptions

[transformer]: #function-transformernode-file-next

[next]: #function-nexterr-tree-file

[freeze]: #processorfreeze

[plugin]: #plugin

[run-done]: #function-doneerr-node-file

[process-done]: #function-doneerr-file

[contribute]: #contribute

[rehype-react]: https://github.com/rhysd/rehype-react

[trough]: https://github.com/wooorm/trough#function-fninput-next

[promise]: https://developer.mozilla.org/Web/JavaScript/Reference/Global_Objects/Promise

[remark-plugins]: https://github.com/remarkjs/remark/blob/master/doc/plugins.md#list-of-plugins

[rehype-plugins]: https://github.com/rehypejs/rehype/blob/master/doc/plugins.md#list-of-plugins

[retext-plugins]: https://github.com/retextjs/retext/blob/master/doc/plugins.md#list-of-plugins

[stream]: https://github.com/unifiedjs/unified-stream

[ideas]: https://github.com/unifiedjs/ideas

[preliminary]: https://github.com/retextjs/retext/commit/8fcb1f#diff-168726dbe96b3ce427e7fedce31bb0bc

[externalised]: https://github.com/remarkjs/remark/commit/9892ec#diff-168726dbe96b3ce427e7fedce31bb0bc

[published]: https://github.com/unifiedjs/unified/commit/2ba1cf

[ware]: https://github.com/segmentio/ware

[gatsby]: https://www.gatsbyjs.org

[mdx]: https://mdxjs.com

[jsx]: https://reactjs.org/docs/jsx-in-depth.html

[prettier]: https://prettier.io

[node.js]: https://nodejs.org

[zeit]: https://zeit.co

[netlify]: https://www.netlify.com

[github]: https://github.com

[mozilla]: https://www.mozilla.org

[wordpress]: https://wordpress.com

[adobe]: https://www.adobe.com

[facebook]: https://www.facebook.com

[google]: https://www.google.com
