# Bublé

## The blazing fast, batteries-included ES2015 compiler

* Try it out at [buble.surge.sh](https://buble.surge.sh)
* Read the docs at [buble.surge.sh/guide](https://buble.surge.sh/guide)


## Quickstart

Via the command line...

```bash
npm install -g buble
buble input.js > output.js
```

...or via the JavaScript API:

```js
var buble = require( 'buble' );
var result = buble.transform( source ); // { code: ..., map: ... }
```


## License

MIT
