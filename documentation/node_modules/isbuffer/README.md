
# isBuffer

Check if something is a [Node.js Buffer](http://nodejs.org/api/buffer.html) or
[Typed Array](https://developer.mozilla.org/en-US/docs/JavaScript/Typed_arrays)

## Usage

```js
var isBuffer = require('isbuffer');

isBuffer(new Buffer(3)); // => true
isBuffer(new Int8Array()); // => true
isBuffer(['foo']); // => false
```

## Api

### isBuffer(obj)

Return true if `obj` is a `Buffer` or `TypedArray`, otherwise return false.

## Installation

With [npm](http://npmjs.org) do

```bash
$ npm install isbuffer
```

## License

(MIT)

Copyright (c) 2013 Julian Gruber &lt;julian@juliangruber.com&gt;

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
