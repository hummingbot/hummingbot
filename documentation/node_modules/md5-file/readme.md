# MD5 file

Get the MD5-sum of a given file, with low memory usage, even on huge files.

## Installation

```sh
npm install --save md5-file
```

## Usage

### As a module

```js
const md5File = require('md5-file')

/* Async usage */
md5File('LICENSE.md').then((hash) => {
  console.log(`The MD5 sum of LICENSE.md is: ${hash}`)
})

/* Sync usage */
const hash = md5File.sync('LICENSE.md')
console.log(`The MD5 sum of LICENSE.md is: ${hash}`)
```

### As a command line tool

```sh
$ md5-file LICENSE.md
ad1faf9381e43c471dc381c17a4ee4b6
```

## API

### `md5File(path: string) => Promise<string>`

Asynchronously get the MD5-sum of the file at `path`.

Returns a [`Promise`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise) that will be resolved with a string containing the MD5-sum.

### `md5File.sync(path: string) => string`

Synchronously get the MD5-sum of the file at `path`.

### License

MIT
