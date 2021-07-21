# entity-decode

This purpose of this library is to provide a single interface to browser and node decode implementation.

It is using the following two underlying implementations:
- Browser: micro decode implementation using browser's NodeElement.textContent method
- Node: [he](https://github.com/mathiasbynens/he)

## Example usage

```js
// Load default implementation
var decode = require('entity-decode');

// Load specific version
var decode = require('entity-decode/browser') // browser version
var decode = require('entity-decode/node') // node version

decode('foo &copy; bar &ne; baz &#x1D306; qux') 
// returns 'foo © bar ≠ baz 𝌆 qux'
```

## License

entity-decode is available under the [MIT](https://mths.be/mit) license.
