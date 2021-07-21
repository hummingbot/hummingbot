# Try to Catch [![NPM version][NPMIMGURL]][NPMURL] [![Dependency Status][DependencyStatusIMGURL]][DependencyStatusURL] [![Build Status][BuildStatusIMGURL]][BuildStatusURL] [![Coverage Status][CoverageIMGURL]][CoverageURL]

[NPMIMGURL]:                https://img.shields.io/npm/v/try-to-catch.svg?style=flat&longCache=true
[BuildStatusIMGURL]:        https://img.shields.io/travis/coderaiser/try-to-catch/master.svg?style=flat&longCache=true
[DependencyStatusIMGURL]:   https://img.shields.io/david/coderaiser/try-to-catch.svg?style=flat&longCache=true
[NPMURL]:                   https://npmjs.org/package/try-to-catch "npm"
[BuildStatusURL]:           https://travis-ci.org/coderaiser/try-to-catch  "Build Status"
[DependencyStatusURL]:      https://david-dm.org/coderaiser/try-to-catch "Dependency Status"

[CoverageURL]:              https://coveralls.io/github/coderaiser/try-to-catch?branch=master
[CoverageIMGURL]:           https://coveralls.io/repos/coderaiser/try-to-catch/badge.svg?branch=master&service=github

Functional `try-catch` wrapper for `promises`.

## Install

```
npm i try-to-catch
```

## API

### tryToCatch(fn, [...args])

Wrap function to avoid `try-catch` block, resolves `[error, result]`;

### Example

Simplest example with `async-await`:

```js
const tryToCatch = require('try-to-catch');
await tryToCatch(Promise.reject('hi'));
// returns
[ Error: hi]
```

Can be used with functions:

```js
const tryToCatch = require('try-to-catch');
await tryToCatch(() => 5);
// returns
[null, 5]
```

Advanced example:

```js
const fs = require('fs');
const tryToCatch = require('try-to-catch');
const {promisify} = require('util');
const readFile = promisify(fs.readFile);
const readDir = promisify(fs.readdir);

read(process.argv[2])
    .then(console.log)
    .catch(console.error);

async function read(path) {
    const [error, data] = await tryToCatch(readFile, path, 'utf8');
    
    if (!error)
        return data;
    
    if (error.code !== 'EISDIR')
        return error;
    
    return await readDir(path);
}
```

## Environments

In old `node.js` environments that not fully supports `es2015`, `try-to-catch` can be used with:

```js
var tryToCatch = require('try-to-catch/legacy');
```

## Related

- [try-catch](https://github.com/coderaiser/try-catch "try-catch") - functional try-catch wrapper.

## License

MIT

