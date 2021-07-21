# hex2rgba

[![NPM](https://nodei.co/npm/hex2rgba.png)](https://nodei.co/npm/hex2rgba/)

[![NPM version](https://img.shields.io/npm/v/hex2rgba.svg)](https://www.npmjs.com/package/hex2rgba)
[![Build Status](https://travis-ci.org/remarkablemark/hex2rgba.svg?branch=master)](https://travis-ci.org/remarkablemark/hex2rgba)
[![Coverage Status](https://coveralls.io/repos/github/remarkablemark/hex2rgba/badge.svg?branch=master)](https://coveralls.io/github/remarkablemark/hex2rgba?branch=master)

Converts hexadecimal to RGBA:

```
hex2rgba(hexadecimal[, alpha])
```

#### Example:

```js
var hex2rgba = require('hex2rgba');
hex2rgba('#f00');         // 'rgba(255,0,0,1)'
hex2rgba('BADA55', 0.42); // 'rgba(186,218,85,0.42)'
```

## Install

```sh
$ npm install hex2rgba
```

## Testing

```sh
$ npm test
$ npm run lint
```

## License

[MIT](https://github.com/remarkablemark/hex2rgba/blob/master/LICENSE)
