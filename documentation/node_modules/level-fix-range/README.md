# level-fix-range

make reverse ranges easier to use.

## Stability

Stable: Expect patches, possible features additions.

## Example

When you use reverse ranges, you have to reverse the `start` and `end` also,

``` js
db.createReadStream({start: 'a', end: 'z'})
db.createReadStream({start: 'z', end: 'a', reverse: true})
```

this is confusing and bug-ridden.

level-fix-range fixes the options so they always make sense.
if you want a range to reverse, just set reverse.

``` js
var fix = require('level-fix-range')
db.createReadStream({start: 'a', end: 'z'})
db.createReadStream(fix({start: 'a', end: 'z', reverse: true}))
```

When you either `start` _OR_ `end`, and the order is `reversed: true`,
it will also reverse the range,
so that:

``` js
{start: X, end: null} //from X to end of database
{start: null, end: X} //from start of database to X
```
and you will get the some data, whether you have reverse=true|false,
but only the order will change.

## License

MIT
