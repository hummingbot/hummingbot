# fastest-stable-stringify

Deterministic `JSON.stringify()` - fastest stable JSON stringifier.


## Installation

With [npm](https://npmjs.org) do:

```
npm install fastest-stable-stringify
```

## Usage

```js
var stringify = require('fastest-stable-stringify');
var str = stringify({foo: 'bar'});
```


## Benchmark

To run benchmark

```
node benchmark
```

Results

```
fastest-stable-stringify x 11,629 ops/sec ±0.67% (92 runs sampled)
fast-stable-stringify x 11,352 ops/sec ±0.63% (91 runs sampled)
fast-json-stable-stringify x 10,085 ops/sec ±0.52% (91 runs sampled)
faster-stable-stringify x 8,645 ops/sec ±0.62% (87 runs sampled)
json-stable-stringify x 7,761 ops/sec ±0.61% (86 runs sampled)
The fastest is fastest-stable-stringify
```


## License

[MIT](./LICENSE)
