# single-trailing-newline [![Build Status](https://secure.travis-ci.org/johnotander/single-trailing-newline.png?branch=master)](https://travis-ci.org/johnotander/single-trailing-newline) [![js-standard-style](https://img.shields.io/badge/code%20style-standard-brightgreen.svg?style=flat)](https://github.com/feross/standard)

Ensure a string has a single trailing newline based off it's dominant newline character.

## Installation

```bash
npm install --save single-trailing-newline
```

## Usage

```javascript
var singleTrailingNewline = require('single-trailing-newline')

singleTrailingNewline('foo\nbar')  // => 'foo\nbar\n'
singleTrailingNewline('foo\nbar\n\n')  // => 'foo\nbar\n'
singleTrailingNewline('foo\r\nbar')  // => 'foo\r\nbar\r\n'
singleTrailingNewline('foo\r\nbar\n\n\n\n')  // => 'foo\r\nbar\n'
```

## License

MIT

## Contributing

1. Fork it
2. Create your feature branch (`git checkout -b my-new-feature`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin my-new-feature`)
5. Create new Pull Request

Crafted with <3 by John Otander ([@4lpine](https://twitter.com/4lpine)).

***

> This package was initially generated with [yeoman](http://yeoman.io) and the [p generator](https://github.com/johnotander/generator-p.git).
