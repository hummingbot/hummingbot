# bufferutil

[![Version npm](https://img.shields.io/npm/v/bufferutil.svg)](https://www.npmjs.com/package/bufferutil)
[![Linux/macOS Build](https://travis-ci.org/websockets/bufferutil.svg?branch=master)](https://travis-ci.org/websockets/bufferutil)
[![Windows Build](https://ci.appveyor.com/api/projects/status/github/websockets/bufferutil?branch=master&svg=true)](https://ci.appveyor.com/project/lpinca/bufferutil)

`bufferutil` is what makes `ws` fast. It provides some utilities to efficiently
perform some operations such as masking and unmasking the data payload of
WebSocket frames.

## Installation

```
npm install bufferutil --save-optional
```

The `--save-optional` flag tells npm to save the package in your package.json
under the [`optionalDependencies`](https://docs.npmjs.com/files/package.json#optionaldependencies)
key.

## API

The module exports two functions.

### `bufferUtil.mask(source, mask, output, offset, length)`

Masks a buffer using the given masking-key as specified by the WebSocket
protocol.

#### Arguments

- `source` - The buffer to mask.
- `mask` - A buffer representing the masking-key.
- `output` - The buffer where to store the result.
- `offset` - The offset at which to start writing.
- `length` - The number of bytes to mask.

#### Example

```js
'use strict';

const bufferUtil = require('bufferutil');
const crypto = require('crypto');

const source = crypto.randomBytes(10);
const mask = crypto.randomBytes(4);

bufferUtil.mask(source, mask, source, 0, source.length);
```

### `bufferUtil.unmask(buffer, mask)`

Unmasks a buffer using the given masking-key as specified by the WebSocket
protocol.

#### Arguments

- `buffer` - The buffer to unmask.
- `mask` - A buffer representing the masking-key.

#### Example

```js
'use strict';

const bufferUtil = require('bufferutil');
const crypto = require('crypto');

const buffer = crypto.randomBytes(10);
const mask = crypto.randomBytes(4);

bufferUtil.unmask(buffer, mask);
```

## License

[MIT](LICENSE)
