# detect-newline [![Build Status](https://travis-ci.org/sindresorhus/detect-newline.svg?branch=master)](https://travis-ci.org/sindresorhus/detect-newline)

> Detect the dominant newline character of a string


## Install

```sh
$ npm install --save detect-newline
```


## Usage

```js
var detectNewline = require('detect-newline');

detectNewline('foo\nbar\nbaz\r\n');
//=> \n
```


## CLI

```sh
$ npm install --global detect-newline
```

```sh
$ detect-newline --help

  Usage
    detect-newline <string>
    cat unicorn.txt | detect-newline

  Example
    detect-newline "$(printf 'Unicorns\nRainbows')"
    \n
```


## License

MIT © [Sindre Sorhus](http://sindresorhus.com)
