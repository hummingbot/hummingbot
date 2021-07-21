Minify [![License][LicenseIMGURL]][LicenseURL] [![Dependency Status][DependencyStatusIMGURL]][DependencyStatusURL] [![Build Status][BuildStatusIMGURL]][BuildStatusURL] [![NPM version][NPMIMGURL]][NPMURL]
===============
[NPMIMGURL]:                https://img.shields.io/npm/v/minify.svg?style=flat
[BuildStatusIMGURL]:        https://img.shields.io/travis/coderaiser/minify/master.svg?style=flat
[DependencyStatusIMGURL]:   https://img.shields.io/david/coderaiser/minify.svg?style=flat
[LicenseIMGURL]:            https://img.shields.io/badge/license-MIT-317BF9.svg?style=flat
[NPM_INFO_IMG]:             https://nodei.co/npm/minify.png?stars
[NPMURL]:                   http://npmjs.org/package/minify
[LicenseURL]:               https://tldrlegal.com/license/mit-license "MIT License"
[BuildStatusURL]:           http://travis-ci.org/coderaiser/minify  "Build Status"
[DependencyStatusURL]:      https://david-dm.org/coderaiser/minify "Dependency Status"

[Minify](http://coderaiser.github.io/minify "Minify") - a minifier of js, css, html and img files.
To use `minify` as middleware try [Mollify](https://github.com/coderaiser/node-mollify "Mollify").

## Install

```
npm i minify -g
```

## How to use?

### CLI

```js
$ cat > hello.js
const hello = 'world';

for (let i = 0; i < hello.length; i++) {
    console.log(hello[i]);
}
^D

$ minify hello.js
const hello="world";for(let l=0;l<hello.length;l++)console.log(hello[l]);
```

### Code Example

`minify` can be used as a `promise`:

```js
const minify = require('minify');

minify('./client.js')
    .then(console.log)
    .catch(console.error);

```

Or with `async-await` and [try-to-catch](https://github.com/coderaiser/try-to-catch'):

```js
const minify = require('minify');
const tryToCatch = require('try-to-catch');

async () => {
    const [error, data] = await tryToCatch(minify, './client.js');
    
    if (error)
        return console.error(error.message);
    
    console.log(data);
}();
```

## License

MIT

