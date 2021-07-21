rollup-plugin-node-globals
===

Plugin to insert node globals including so code that works with browserify should work even if it uses process or buffers. This is based on [rollup-plugin-inject
](https://github.com/rollup/rollup-plugin-inject).

- process
- global
- Buffer
- `__dirname`
- `__filename`

Plus `process.nextTick` and `process.browser` are optimized to only pull in
themselves and `__dirname` and `__filename` point to the file on disk

There are a few options to control output
- `process` - pass `false` to disable process polyfilling
- `global` - pass `false` to disable global polyfilling
- `buffer` - pass `false` to disable Buffer polyfilling
- `dirname` - pass `false` to disable `__dirname` polyfilling
- `filename` - pass `false` to disable `__filename` polyfilling
- `baseDir` which is used for resolving `__dirname` and `__filename`.

# examples

```js
var foo;
if (process.browser) {
  foo = 'bar';
} else {
  foo = 'baz';
}
```

turns into

```js
import {browser} from 'path/to/process';
var foo;
if (browser) {
  foo = 'bar';
} else {
  foo = 'baz';
}
```

but with rollup that ends up being

```js
var browser = true;
var foo;
if (browser) {
  foo = 'bar';
} else {
  foo = 'baz';
}
```

or

```js
var timeout;
if (global.setImmediate) {
  timeout = global.setImmediate;
} else {
  timeout = global.setTimeout;
}
export default timeout;
```

turns into

```js
import {_global} from 'path/to/global.js';
var timeout;
if (_global.setImmediate) {
  timeout = _global.setImmediate;
} else {
  timeout = _global.setTimeout;
}
export default timeout;

```

which rollup turns into

```js
var _global = typeof global !== "undefined" ? global :
            typeof self !== "undefined" ? self :
            typeof window !== "undefined" ? window : {}

var timeout;
if (_global.setImmediate) {
  timeout = _global.setImmediate;
} else {
  timeout = _global.setTimeout;
}
var timeout$1 = timeout;

export default timeout$1;
```

With that top piece only showing up once no matter how many times global was used.
