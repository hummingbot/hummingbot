# node-gyp-build

Build tool and bindings loader for node-gyp that supports prebuilds.

```
npm install node-gyp-build
```

Use together with [prebuildify](https://github.com/mafintosh/prebuildify) to easily support prebuilds for your native modules.

## Usage

`node-gyp-build` works similar to `node-gyp build` except that it will check if a build or prebuild is present before rebuilding your project.

It's main intended use is as an npm install script and bindings loader for native modules that bundle prebuilds using [prebuildify](https://github.com/mafintosh/prebuildify).

First add `node-gyp-build` as an install script to your native project

``` js
{
  ...
  "scripts": {
    "install": "node-gyp-build"
  }
}
```

Then in your `index.js`, instead of using the [bindings module](https://www.npmjs.com/package/bindings) use `node-gyp-build` to load your binding.

``` js
var binding = require('node-gyp-build')(__dirname)
```

If you do these two things and bundle prebuilds [prebuildify](https://github.com/mafintosh/prebuildify) your native module will work for most platforms
without having to compile on install time AND will work in both node and electron without the need to recompile between usage.

Users can override `node-gyp-build` and force compiling by doing `npm install --build-from-source`.

## License

MIT
