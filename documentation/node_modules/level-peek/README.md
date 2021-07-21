# level-peek

peek the first or last record in a leveldb range.

## example

``` js
var levelup = require('levelup')
var db = levelup(PATH_TO_DB)

var peek = require('level-peek')

//get the first value, 'a' or after
peek.first(db, {start: 'a'}, function (err, key, value) {
  console.log(key, value)
})

//get last value, 'z' or before.
peek.last(db, {end: 'z'}, function (err, key, value) {
  console.log(key, value)
})
```


see also, [level-fix-range](https://github.com/dominictarr/level-fix-range)
and https://github.com/rvagg/node-levelup/issues/110

## License

MIT
