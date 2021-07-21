# rollup-plugin-commonjs [![Build Status][travis-img]][travis]

[travis-img]: https://travis-ci.org/rollup/rollup-plugin-commonjs.svg
[travis]: https://travis-ci.org/rollup/rollup-plugin-commonjs

Convert CommonJS modules to ES6, so they can be included in a Rollup bundle


## Installation

```bash
npm install --save-dev rollup-plugin-commonjs
```


## Usage

Typically, you would use this plugin alongside [rollup-plugin-node-resolve](https://github.com/rollup/rollup-plugin-node-resolve), so that you could bundle your CommonJS dependencies in `node_modules`.

```js
// rollup.config.js
import commonjs from 'rollup-plugin-commonjs';
import nodeResolve from 'rollup-plugin-node-resolve';

export default {
  input: 'main.js',
  output: {
    file: 'bundle.js',
    format: 'iife'
  },
  plugins: [
    nodeResolve({
      jsnext: true,
      main: true
    }),

    commonjs({
      // non-CommonJS modules will be ignored, but you can also
      // specifically include/exclude files
      include: 'node_modules/**',  // Default: undefined
      exclude: [ 'node_modules/foo/**', 'node_modules/bar/**' ],  // Default: undefined
      // these values can also be regular expressions
      // include: /node_modules/

      // search for files other than .js files (must already
      // be transpiled by a previous plugin!)
      extensions: [ '.js', '.coffee' ],  // Default: [ '.js' ]

      // if true then uses of `global` won't be dealt with by this plugin
      ignoreGlobal: false,  // Default: false

      // if false then skip sourceMap generation for CommonJS modules
      sourceMap: false,  // Default: true

      // explicitly specify unresolvable named exports
      // (see below for more details)
      namedExports: { 'react': ['createElement', 'Component' ] },  // Default: undefined

      // sometimes you have to leave require statements
      // unconverted. Pass an array containing the IDs
      // or a `id => boolean` function. Only use this
      // option if you know what you're doing!
      ignore: [ 'conditional-runtime-dependency' ]
    })
  ]
};
```

### Usage with symlinks

Symlinks are common in monorepos and are also created by the `npm link` command. Rollup with `rollup-plugin-node-resolve` resolves modules to their real paths by default. So `include` and `exclude` paths should handle real paths rather than symlinked paths (e.g. `../common/node_modules/**` instead of `node_modules/**`). You may also use a regular expression for `include` that works regardless of base path. Try this:

```
commonjs({
  include: /node_modules/
})
```

Whether symlinked module paths are [realpathed](http://man7.org/linux/man-pages/man3/realpath.3.html) or preserved depends on Rollup's `preserveSymlinks` setting, which is false by default, matching Node.js' default behavior. Setting `preserveSymlinks` to true in your Rollup config will cause `import` and `export` to match based on symlinked paths instead.

### Custom named exports

This plugin will attempt to create named exports, where appropriate, so you can do this...

```js
// importer.js
import { named } from './exporter.js';

// exporter.js
module.exports = { named: 42 }; // or `exports.named = 42;`
```

...but that's not always possible:

```js
// importer.js
import { named } from 'my-lib';

// my-lib.js
var myLib = exports;
myLib.named = 'you can\'t see me';
```

In those cases, you can specify custom named exports:

```js
commonjs({
  namedExports: {
    // left-hand side can be an absolute path, a path
    // relative to the current directory, or the name
    // of a module in node_modules
    'my-lib': [ 'named' ]
  }
})
```


## Strict mode

ES modules are *always* parsed in strict mode. That means that certain non-strict constructs (like octal literals) will be treated as syntax errors when Rollup parses modules that use them. Some older CommonJS modules depend on those constructs, and if you depend on them your bundle will blow up. There's basically nothing we can do about that.

Luckily, there is absolutely no good reason *not* to use strict mode for everything — so the solution to this problem is to lobby the authors of those modules to update them.


## License

MIT
