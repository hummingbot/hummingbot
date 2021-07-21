rollup-plugin-node-builtins
===

```
npm install --save-dev rollup-plugin-node-builtins
```

Allows the node builtins to be `require`d/`import`ed. Doing so gives the proper shims to support modules that were designed for Browserify, some modules require [rollup-plugin-node-globals](https://github.com/calvinmetcalf/rollup-plugin-node-globals).

The following modules include ES6 specific version which allow you to do named imports in addition to the default import and should work fine if you only use this plugin.

- process*
- events
- stream*
- util*
- path
- buffer*
- querystring
- url*
- string_decoder*
- punycode
- http*†
- https*†
- os*
- assert*
- constants
- timers*
- console*‡
- vm*§
- zlib*
- tty
- domain
- dns∆
- dgram∆
- child_process∆
- cluster∆
- module∆
- net∆
- readline∆
- repl∆
- tls∆
- fs˚
- crypto˚

\* requires [node-globals plugin](https://github.com/calvinmetcalf/rollup-plugin-node-globals)

† the http and https modules are actually the same and don't differentiate based on protocol

‡ default export only, because it's console, seriously just use the global

§ vm does not have all corner cases and has less of them in a web worker

∆ not shimmed, just returns mock

˚ optional, add option to enable browserified shim

Crypto is not shimmed and and we just provide the commonjs one from browserify  and it will likely not work, if you really want it please pass `{crypto: true}` as an option.



Not all included modules rollup equally, streams (and by extension anything that requires it like http) are a mess of circular references that are pretty much impossible to tree-shake out, similarly url methods are actually a shortcut to a url object so those methods don't tree shake out very well, punycode, path, querystring, events, util, and process tree shake very well especially if you do named imports.

config for using this with something simple like events or querystring

```js
import builtins from 'rollup-plugin-node-builtins';
rollup({
  entry: 'main.js',
  plugins: [
    builtins()
  ]
})
```

and now if main contains this, it should just work

```js
import EventEmitter from 'events';
import {inherits} from 'util';

// etc
```

Config for something more complicated like http

```js
import builtins from 'rollup-plugin-node-builtins';
import globals from 'rollup-plugin-node-globals';
rollup({
  entry: 'main.js',
  plugins: [
    globals(),
    builtins()
  ]
})
```

License
===

MIT except ES6 ports of browserify modules which are whatever the original library was.
