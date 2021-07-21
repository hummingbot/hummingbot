# string-range

Check whether a string is within a range.

## Example

``` js
var ranges = require('string-range')

ranges.satisfies('hello', {min: 'a', max: 'z'})
=> true
ranges.satisfies('Hello', {min: 'a', max: 'z'})
=> false

//force a range inside a prefix!

ranges.satisfies('TYPE~key', ranges.prefix({min:'a', max:'z'}, 'TYPE')
=> true
```

`min` and `max` are alaises for `start` and `end`.

## License

MIT
