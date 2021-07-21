# Pre/Post hooks for leveldb

Intercept put/delete/batch operations on levelup.

## Warning - Breaking Changes
 
The API for implementing pre hooks has changed.
Instead of mutating an array at once, the prehook
is called on each change `hook(change, add)`
and may call `add(_change)` to add a new item into the batch.

Also, attaching hooks to leveldb is now simpler
``` js
var Hooks = require('level-hooks')
Hooks(db) //previously: Hooks()(db)
```

## Example

``` js
var levelup   = require('levelup')
var timestamp = require('monotonic-timestamp')
var hooks     = require('level-hooks')

levelup(file, {createIfMissing: true}, function (err, db) {

  //install hooks onto db.
  hooks(db)

  db.hooks.pre({start: '', end: '~'}, function (change, add) {
    //change is same pattern as the an element in the batch array.
    //add a log to record every put operation.
    add({type: 'put', key: '~log-'+timestamp()+'-'+change.type, value: change.key})
  })

  //add a hook that responds after an operation has completed.
  db.hooks.post(function (ch) {
    //{type: 'put'|'del', key: ..., value: ...}
  })

})
```

Used by [map-reduce](https://github.com/dominictarr/map-reduce) 
to make map-reduce durable across crashes!

## API

### rm = db.hooks.pre (range?, hook(change, add(op), batch))

If `prefix` is a `string` or `object` that defines the range the pre-hook triggers on.
If `prefix' is a string, then the hook only triggers on keys that _start_ with that 
string. If the hook is an object it must be of form `{start: START, end: END}`

`hook` is a function, and will be called on each item in the batch 
(if it was a `put` or `del`, it will be called on the change)
`op` is always of the form `{key: key, value: value, type:'put' | 'del'}`

Pass additional changes to `add` to add them to the batch.
If add is passed a string as the second argument it will prepend that prefix
to any keys you add.

You can check what opperations are currently in the batch with the third argument.
Do not modify the `batch` directly, instead use `add`

To veto (remove) the current change call `add(false)`.

`db.hooks.pre` returns a function that will remove the hook when called.

#### unsafe mode

normally, pre hooks prevent you from inserting into the hooked range
when the hook is triggered. However, sometimes you do need to do this.
In those cases, pass in a range with `{start: START, end: END, safe: false}`
and level-hooks will not error. If you use this option, your hook must
avoid triggering in a loop itself.

### rm = db.hooks.post (range?, hook)

Post hooks do not offer any chance to change the value.
but do take a range option, just like `pre`

`db.hooks.post` returns a function that will remove the hook when called.


## License

MIT
