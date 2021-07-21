# native-url

A lightweight implementation of Node's [url](http://nodejs.org/api/url.html) interface atop the [URL API](https://developer.mozilla.org/en-US/docs/Web/API/URL). Use it instead of the `url` module to reduce your bundle size by around 7.5 kB.

Weighs **1.6 kB gzipped**, works in Node.js 7+ and [all modern browsers](https://caniuse.com/#feat=mdn-api_url):

![Chrome 32, Firefox 19, Safari 7, Edge 12, Opera 19](https://badges.herokuapp.com/browsers?googlechrome=32&firefox=19&safari=7&microsoftedge=12&opera=19)

Older browsers can be [easily polyfilled](#polyfill-for-older-browsers) without new browsers loading the code.

## Installation

```sh
npm i native-url
```

## Usage

```js
const url = require('native-url');

url.parse('https://example.com').host // example.com
url.parse('/?a=b', true).query // { a: 'b' }
```

### Usage with Webpack

When you use the `url` module, webpack bundles [`node-url`](https://github.com/defunctzombie/node-url) for the browser. You can alias webpack to use `native-url` instead, saving around 7.5kB:

```js
// webpack.config.js
module.exports = {
  // ...
  resolve: {
    alias: {
      url: 'native-url'
    }
  }
}
```

The result is **functionally equivalent** in Node 7+ and all modern browsers.

### Usage with Rollup

Rollup does not bundle shims for Node.js modules like `url` by default, but we can add `url` support via `native-url` using aliases:

```js
// rollup.config.js
import resolve from 'rollup-plugin-node-resolve';
import alias from '@rollup/plugin-alias';

module.exports = {
  // ...
  plugins: [
    resolve(),
    alias({
      entries: {
        url: 'native-url'
      }
    })
  ]
};
```

With this in place, `import url from 'url'` will use `native-url` and keep your bundle small.

## API

Refer Node's [legacy url documentation](https://nodejs.org/api/url.html#url_legacy_url_api) for detailed API documentation.

### `url.parse(urlStr, [parseQueryString], [slashesDenoteHost])`

Parses a URL string and returns a URL object representation:

```js
url.parse('https://example.com');
// {
//   href: 'http://example.com/',
//   protocol: 'http:',
//   slashes: true,
//   host: 'example.com',
//   hostname: 'example.com',
//   query: {},
//   search: null,
//   pathname: '/',
//   path: '/'
// }

url.parse('/foo?a=b', true).query.a; // "b"
```

### `url.format(urlObj)`

Given a parsed URL object, returns its corresponding URL string representation:

```js
url.format({ protocol: 'https', host: 'example.com' });
// "https://example.com"
```

### `url.resolve(from, to)`

Resolves a target URL based on the provided base URL:

```js
url.resolve('/a/b', 'c');
// "/a/b/c"
url.resolve('/a/b', '/c#d');
// "/c#d"
```

## Polyfill for Older Browsers

`native-url` relies on the DOM [URL API](https://developer.mozilla.org/en-US/docs/Web/API/URL) to work. For older browsers that don't support the `URL` API, a [polyfill](https://www.npmjs.com/package/url-polyfill) is available.

Conveniently, a polyfill is never needed for [browsers that support ES Modules](https://caniuse.com/#feat=es6-module), so we can use `<script nomodule>` to conditionally load it for older browsers:

```html
<script nomodule src="/path/to/url-polyfill.js"></script>
```
