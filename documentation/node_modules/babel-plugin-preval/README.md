<div align="center">
<h1>babel-plugin-preval</h1>

Pre-evaluate code at build-time

</div>

<hr />

<!-- prettier-ignore-start -->

[![Build Status][build-badge]][build]
[![Code Coverage][coverage-badge]][coverage]
[![version][version-badge]][package]
[![downloads][downloads-badge]][npmtrends]
[![MIT License][license-badge]][license]

[![All Contributors](https://img.shields.io/badge/all_contributors-14-orange.svg?style=flat-square)](#contributors)
[![PRs Welcome][prs-badge]][prs]
[![Code of Conduct][coc-badge]][coc]
[![Babel Macro][macros-badge]][babel-plugin-macros]
[![Examples][examples-badge]][examples]

[![Watch on GitHub][github-watch-badge]][github-watch]
[![Star on GitHub][github-star-badge]][github-star]
[![Tweet][twitter-badge]][twitter]

<!-- prettier-ignore-end -->

## The problem

You need to do some dynamic stuff, but don't want to do it at runtime. Or maybe
you want to do stuff like read the filesystem to get a list of files and you
can't do that in the browser.

## This solution

This allows you to specify some code that runs in Node and whatever you
`module.exports` in there will be swapped. For example:

```js
const x = preval`module.exports = 1`

//      ↓ ↓ ↓ ↓ ↓ ↓

const x = 1
```

Or, more interestingly:

```javascript
const x = preval`
  const fs = require('fs')
  const val = fs.readFileSync(__dirname + '/fixture1.md', 'utf8')
  module.exports = {
    val,
    getSplit: function(splitDelimiter) {
      return x.val.split(splitDelimiter)
    }
  }
`

//      ↓ ↓ ↓ ↓ ↓ ↓

const x = {
  val: '# fixture\n\nThis is some file thing...\n',
  getSplit: function getSplit(splitDelimiter) {
    return x.val.split(splitDelimiter)
  },
}
```

There's also `preval.require('./something')` and
`import x from /* preval */ './something'` (which can both take some arguments)
or add `// @preval` comment at the top of a file.

See more below.

## Table of Contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Installation](#installation)
- [Usage](#usage)
  - [Template Tag](#template-tag)
  - [import comment](#import-comment)
  - [preval.require](#prevalrequire)
  - [preval file comment (`// @preval`)](#preval-file-comment--preval)
- [Configure with Babel](#configure-with-babel)
  - [Via `.babelrc` (Recommended)](#via-babelrc-recommended)
  - [Via CLI](#via-cli)
  - [Via Node API](#via-node-api)
- [Use with `babel-plugin-macros`](#use-with-babel-plugin-macros)
- [Examples](#examples)
- [Notes](#notes)
- [FAQ](#faq)
  - [How is this different from prepack?](#how-is-this-different-from-prepack)
  - [How is this different from webpack loaders?](#how-is-this-different-from-webpack-loaders)
- [Inspiration](#inspiration)
- [Related Projects](#related-projects)
- [Other Solutions](#other-solutions)
- [Contributors](#contributors)
- [LICENSE](#license)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Installation

This module is distributed via [npm][npm] which is bundled with [node][node] and
should be installed as one of your project's `devDependencies`:

```
npm install --save-dev babel-plugin-preval
```

## Usage

Important notes:

1.  All code run by `preval` is _not_ run in a sandboxed environment
2.  All code _must_ run synchronously.
3.  Code that is run by preval is not transpiled so it must run natively in the
    version of node you're running. (cannot use es modules).

> You may like to watch
> [this YouTube video](https://www.youtube.com/watch?v=1queadQ0048&list=PLV5CVI1eNcJgCrPH_e6d57KRUTiDZgs0u)
> to get an idea of what preval is and how it can be used.

### Template Tag

**Before**:

```javascript
const greeting = preval`
  const fs = require('fs')
  module.exports = fs.readFileSync(require.resolve('./greeting.txt'), 'utf8')
`
```

**After** (assuming `greeting.txt` contains the text: `"Hello world!"`):

```javascript
const greeting = 'Hello world!'
```

`preval` can also handle _some_ simple dynamic values as well:

**Before**:

```javascript
const name = 'Bob Hope'
const person = preval`
  const [first, last] = require('./name-splitter')(${name})
  module.exports = {first, last}
`
```

**After** (assuming `./name-splitter` is a function that splits a name into
first/last):

```javascript
const name = 'Bob Hope'
const person = {first: 'Bob', last: 'Hope'}
```

### import comment

**Before**:

```javascript
import fileList from /* preval */ './get-list-of-files'
```

**After** (depending on what `./get-list-of-files does`, it might be something
like):

```javascript
const fileList = ['file1.md', 'file2.md', 'file3.md', 'file4.md']
```

You can also provide arguments which themselves are prevaled!

**Before**:

```javascript
import fileList from /* preval(3) */ './get-list-of-files'
```

**After** (assuming `./get-list-of-files` accepts an argument limiting how many
files are retrieved:

```javascript
const fileList = ['file1.md', 'file2.md', 'file3.md']
```

### preval.require

**Before**:

```javascript
const fileLastModifiedDate = preval.require('./get-last-modified-date')
```

**After**:

```javascript
const fileLastModifiedDate = '2017-07-05'
```

And you can provide _some_ simple dynamic arguments as well:

**Before**:

```javascript
const fileLastModifiedDate = preval.require(
  './get-last-modified-date',
  '../../some-other-file.js',
)
```

**After**:

```javascript
const fileLastModifiedDate = '2017-07-04'
```

### preval file comment (`// @preval`)

Using the preval file comment will update a whole file to be evaluated down to
an export.

Whereas the above usages (assignment/import/require) will only preval the scope
of the assignment or file being imported.

**Before**:

```javascript
// @preval

const id = require('./path/identity')
const one = require('./path/one')

const compose = (...fns) => fns.reduce((f, g) => a => f(g(a)))
const double = a => a * 2
const square = a => a * a

module.exports = compose(
  square,
  id,
  double,
)(one)
```

**After**:

```javascript
module.exports = 4
```

## Configure with Babel

### Via `.babelrc` (Recommended)

**.babelrc**

```json
{
  "plugins": ["preval"]
}
```

### Via CLI

```sh
babel --plugins preval script.js
```

### Via Node API

```javascript
require('babel-core').transform('code', {
  plugins: ['preval'],
})
```

## Use with `babel-plugin-macros`

Once you've
[configured `babel-plugin-macros`](https://github.com/kentcdodds/babel-plugin-macros/blob/master/other/docs/user.md)
you can import/require the preval macro at `babel-plugin-preval/macro`. For
example:

```javascript
import preval from 'babel-plugin-preval/macro'

const one = preval`module.exports = 1 + 2 - 1 - 1`
```

> You could also use [`preval.macro`][preval.macro] if you'd prefer to type less
> 😀

## Examples

- [Mastodon](https://github.com/tootsuite/mastodon/pull/4202) saved 40kb
  (gzipped) using `babel-plugin-preval`
- [glamorous-website](https://github.com/kentcdodds/glamorous-website/pull/235)
  uses [`preval.macro`][preval.macro] to determine Algolia options based on
  `process.env.LOCALE`. It also uses [`preval.macro`][preval.macro] to load an
  `svg` file as a string, `base64` encode it, and use it as a `background-url`
  for an input element.
- [Generate documentation for React components](https://gist.github.com/souporserious/575609dc5a5d52e167dd2236079eccc0)
- [Serverless with webpack](https://github.com/geovanisouza92/serverless-preval)
  build serverless functions using webpack and Babel for development and
  production with preval to replace (possible sensible) content in code.
- [Read files at build time (video)](https://www.youtube.com/watch?v=NhmrbpVKgdQ&feature=youtu.be)

## Notes

If you use `babel-plugin-transform-decorators-legacy`, there is a conflict
because both plugins must be placed at the top

Wrong:

```json
{
  "plugins": ["preval", "transform-decorators-legacy"]
}
```

Ok:

```json
{
  "plugins": ["preval", ["transform-decorators-legacy"]]
}
```

## FAQ

### How is this different from prepack?

[`prepack`][prepack] is intended to be run on your final bundle after you've run
your webpack/etc magic on it. It does a TON of stuff, but the idea is that your
code should work with or without prepack.

`babel-plugin-preval` is intended to let you write code that would _not_ work
otherwise. Doing things like reading something from the file system are not
possible in the browser (or with prepack), but `preval` enables you to do this.

### How is this different from webpack loaders?

This plugin was inspired by webpack's [val-loader][val-loader]. The benefit of
using this over that loader (or any other loader) is that it integrates with
your existing babel pipeline. This is especially useful for the server where
you're probably not bundling your code with [`webpack`][webpack], but you may be
using babel. (If you're not using either, configuring babel for this would be
easier than configuring webpack for `val-loader`).

In addition, you can implement pretty much any webpack loader using
`babel-plugin-preval`.

If you want to learn more, check `webpack` documentations about
[`loaders`][webpack-loaders].

## Inspiration

I needed something like this for the
[glamorous website](https://github.com/kentcdodds/glamorous-website). I
live-streamed developing the whole thing. If you're interested you can find
[the recording on my youtube channel](https://www.youtube.com/watch?v=3vxov5xUai8&index=19&list=PLV5CVI1eNcJh5CTgArGVwANebCrAh2OUE)
(note, screen only recording, no audio).

I was inspired by the [val-loader][val-loader] from webpack.

## Related Projects

- [`preval.macro`][preval.macro] - nicer integration with `babel-plugin-macros`

## Other Solutions

I'm not aware of any, if you are please [make a pull request][prs] and add it
here!

## Contributors

Thanks goes to these people ([emoji key][emojis]):

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore -->
| [<img src="https://avatars.githubusercontent.com/u/1500684?v=3" width="100px;"/><br /><sub><b>Kent C. Dodds</b></sub>](https://kentcdodds.com)<br />[💻](https://github.com/kentcdodds/babel-plugin-preval/commits?author=kentcdodds "Code") [📖](https://github.com/kentcdodds/babel-plugin-preval/commits?author=kentcdodds "Documentation") [🚇](#infra-kentcdodds "Infrastructure (Hosting, Build-Tools, etc)") [⚠️](https://github.com/kentcdodds/babel-plugin-preval/commits?author=kentcdodds "Tests") | [<img src="https://avatars3.githubusercontent.com/u/5610087?v=3" width="100px;"/><br /><sub><b>Matt Phillips</b></sub>](http://mattphillips.io)<br />[💻](https://github.com/kentcdodds/babel-plugin-preval/commits?author=mattphillips "Code") [📖](https://github.com/kentcdodds/babel-plugin-preval/commits?author=mattphillips "Documentation") [⚠️](https://github.com/kentcdodds/babel-plugin-preval/commits?author=mattphillips "Tests") | [<img src="https://avatars1.githubusercontent.com/u/28024000?v=3" width="100px;"/><br /><sub><b>Philip Oliver</b></sub>](https://twitter.com/philipodev)<br />[🐛](https://github.com/kentcdodds/babel-plugin-preval/issues?q=author%3Aphilipodev "Bug reports") | [<img src="https://avatars2.githubusercontent.com/u/2109702?v=3" width="100px;"/><br /><sub><b>Sorin Davidoi</b></sub>](https://toot.cafe/@sorin)<br />[🐛](https://github.com/kentcdodds/babel-plugin-preval/issues?q=author%3Asorin-davidoi "Bug reports") [💻](https://github.com/kentcdodds/babel-plugin-preval/commits?author=sorin-davidoi "Code") [⚠️](https://github.com/kentcdodds/babel-plugin-preval/commits?author=sorin-davidoi "Tests") | [<img src="https://avatars4.githubusercontent.com/u/1127238?v=4" width="100px;"/><br /><sub><b>Luke Herrington</b></sub>](https://github.com/infiniteluke)<br />[💡](#example-infiniteluke "Examples") | [<img src="https://avatars4.githubusercontent.com/u/22868432?v=4" width="100px;"/><br /><sub><b>Lufty Wiranda</b></sub>](http://instagram.com/luftywiranda13)<br />[💻](https://github.com/kentcdodds/babel-plugin-preval/commits?author=luftywiranda13 "Code") | [<img src="https://avatars0.githubusercontent.com/u/3877773?v=4" width="100px;"/><br /><sub><b>Oscar</b></sub>](http://obartra.github.io)<br />[💻](https://github.com/kentcdodds/babel-plugin-preval/commits?author=obartra "Code") [⚠️](https://github.com/kentcdodds/babel-plugin-preval/commits?author=obartra "Tests") |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| [<img src="https://avatars1.githubusercontent.com/u/14310216?v=4" width="100px;"/><br /><sub><b>pro-nasa</b></sub>](https://github.com/pro-nasa)<br />[📖](https://github.com/kentcdodds/babel-plugin-preval/commits?author=pro-nasa "Documentation") | [<img src="https://avatars0.githubusercontent.com/u/9248479?v=4" width="100px;"/><br /><sub><b>Sergey Bekrin</b></sub>](http://bekrin.me)<br /> | [<img src="https://avatars0.githubusercontent.com/u/18613301?v=4" width="100px;"/><br /><sub><b>Mauro Bringolf</b></sub>](https://maurobringolf.ch)<br />[💻](https://github.com/kentcdodds/babel-plugin-preval/commits?author=maurobringolf "Code") [⚠️](https://github.com/kentcdodds/babel-plugin-preval/commits?author=maurobringolf "Tests") | [<img src="https://avatars1.githubusercontent.com/u/10875678?v=4" width="100px;"/><br /><sub><b>Joe Lim</b></sub>](https://joelim.me)<br />[💻](https://github.com/kentcdodds/babel-plugin-preval/commits?author=xjlim "Code") | [<img src="https://avatars3.githubusercontent.com/u/13483453?v=4" width="100px;"/><br /><sub><b>Marcin Zielinski</b></sub>](https://github.com/marzelin)<br />[💻](https://github.com/kentcdodds/babel-plugin-preval/commits?author=marzelin "Code") | [<img src="https://avatars3.githubusercontent.com/u/1972567?v=4" width="100px;"/><br /><sub><b>Tommy</b></sub>](http://www.tommyleunen.com)<br />[💻](https://github.com/kentcdodds/babel-plugin-preval/commits?author=tleunen "Code") | [<img src="https://avatars0.githubusercontent.com/u/831308?v=4" width="100px;"/><br /><sub><b>Matheus Gonçalves da Silva</b></sub>](https://github.com/PlayMa256)<br />[📖](https://github.com/kentcdodds/babel-plugin-preval/commits?author=PlayMa256 "Documentation") |

<!-- ALL-CONTRIBUTORS-LIST:END -->

This project follows the [all-contributors][all-contributors] specification.
Contributions of any kind welcome!

## LICENSE

MIT

[npm]: https://www.npmjs.com/
[node]: https://nodejs.org
[build-badge]: https://img.shields.io/travis/kentcdodds/babel-plugin-preval.svg?style=flat-square
[build]: https://travis-ci.org/kentcdodds/babel-plugin-preval
[coverage-badge]: https://img.shields.io/codecov/c/github/kentcdodds/babel-plugin-preval.svg?style=flat-square
[coverage]: https://codecov.io/github/kentcdodds/babel-plugin-preval
[version-badge]: https://img.shields.io/npm/v/babel-plugin-preval.svg?style=flat-square
[package]: https://www.npmjs.com/package/babel-plugin-preval
[downloads-badge]: https://img.shields.io/npm/dm/babel-plugin-preval.svg?style=flat-square
[npmtrends]: http://www.npmtrends.com/babel-plugin-preval
[license-badge]: https://img.shields.io/npm/l/babel-plugin-preval.svg?style=flat-square
[license]: https://github.com/kentcdodds/babel-plugin-preval/blob/master/LICENSE
[prs-badge]: https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square
[prs]: http://makeapullrequest.com
[donate-badge]: https://img.shields.io/badge/$-support-green.svg?style=flat-square
[donate]: http://kcd.im/donate
[coc-badge]: https://img.shields.io/badge/code%20of-conduct-ff69b4.svg?style=flat-square
[coc]: https://github.com/kentcdodds/babel-plugin-preval/blob/master/other/CODE_OF_CONDUCT.md
[macros-badge]: https://img.shields.io/badge/babel--macro-%F0%9F%8E%A3-f5da55.svg?style=flat-square
[babel-plugin-macros]: https://github.com/kentcdodds/babel-plugin-macros
[examples-badge]: https://img.shields.io/badge/%F0%9F%92%A1-examples-8C8E93.svg?style=flat-square
[examples]: https://github.com/kentcdodds/babel-plugin-preval/blob/master/other/EXAMPLES.md
[github-watch-badge]: https://img.shields.io/github/watchers/kentcdodds/babel-plugin-preval.svg?style=social
[github-watch]: https://github.com/kentcdodds/babel-plugin-preval/watchers
[github-star-badge]: https://img.shields.io/github/stars/kentcdodds/babel-plugin-preval.svg?style=social
[github-star]: https://github.com/kentcdodds/babel-plugin-preval/stargazers
[twitter]: https://twitter.com/intent/tweet?text=Check%20out%20babel-plugin-preval!%20https://github.com/kentcdodds/babel-plugin-preval%20%F0%9F%91%8D
[twitter-badge]: https://img.shields.io/twitter/url/https/github.com/kentcdodds/babel-plugin-preval.svg?style=social
[emojis]: https://github.com/kentcdodds/all-contributors#emoji-key
[all-contributors]: https://github.com/kentcdodds/all-contributors
[prepack]: https://github.com/facebook/prepack
[preval.macro]: https://github.com/kentcdodds/preval.macro
[webpack]: https://webpack.js.org/
[webpack-loaders]: https://webpack.js.org/concepts/loaders/
[val-loader]: https://github.com/webpack-contrib/val-loader
