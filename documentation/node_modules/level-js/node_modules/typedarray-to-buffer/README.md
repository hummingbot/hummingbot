# typedarray-to-buffer [![travis](https://img.shields.io/travis/feross/typedarray-to-buffer.svg)](https://travis-ci.org/feross/typedarray-to-buffer) [![npm](https://img.shields.io/npm/v/typedarray-to-buffer.svg)](https://npmjs.org/package/typedarray-to-buffer) [![gittip](https://img.shields.io/gittip/feross.svg)](https://www.gittip.com/feross/)

#### Convert a typed array to a [Buffer](https://github.com/feross/buffer) without a copy.

[![testling badge](https://ci.testling.com/feross/typedarray-to-buffer.png)](https://ci.testling.com/feross/typedarray-to-buffer)

Say you're using the ['buffer'](https://github.com/feross/buffer) module on npm, or
[browserify](http://browserify.org/) and you're working with lots of binary data.

Unfortunately, sometimes the browser or someone else's API gives you an `ArrayBuffer`
or a typed array like `Uint8Array` to work with and you need to convert it to a
`Buffer`. What do you do?

Of course: `new Buffer(uint8array)`

But, alas, every time you do `new Buffer(uint8array)` **the entire array gets copied**.
The `Buffer` constructor does a copy; this is
defined by the [node docs](http://nodejs.org/api/buffer.html) and the 'buffer' module
matches the node API exactly.

So, how can we avoid this expensive copy in
[performance critical applications](https://github.com/feross/buffer/issues/22)?

***Simply use this module, of course!***

## install

```bash
npm install typedarray-to-buffer
```

## usage

To convert a typed array to a `Buffer` **without a copy**, do this:

```js
var toBuffer = require('typedarray-to-buffer')

var arr = new Uint8Array([1, 2, 3])
arr = toBuffer(arr)

// arr is a buffer now!

arr.toString()  // '\u0001\u0002\u0003'
arr.readUInt16BE(0)  // 258
```

## how it works

If the browser supports typed arrays, then `toBuffer` will **augment the Uint8Array** you
pass in with the `Buffer` methods and return it. See
[how does Buffer work?](https://github.com/feross/buffer#how-does-it-work) for more about
how augmentation works.

If the browser doesn't support typed arrays, then `toBuffer` will create a new `Buffer`
object, copy the data into it, and return it. There's no simple performance optimization
we can do for old browsers. Oh well.

If this module is used in node, then it will just call `new Buffer`. This is just for
the convenience of modules that work in both node and the browser.

## license

MIT. Copyright (C) [Feross Aboukhadijeh](http://feross.org).
