# async-cache

Cache your async lookups and don't fetch the same thing more than
necessary.

## Example

Let's say you have to look up stat info from paths.  But you are ok
with only looking up the stat info once every 10 minutes (since it
doesn't change that often), and you want to limit your cache size to
1000 objects, and never have two stat calls for the same file
happening at the same time (since that's silly and unnecessary).

You can do this:

```javascript
var stats = new AsyncCache({
  // options passed directly to the internal lru cache
  max: 1000,
  maxAge: 1000 * 60 * 10,
  // method to load a thing if it's not in the cache.
  // key must be unique in the context of this cache.
  load: function (key, cb) {
    // the key can be something like the path, or fd+path, or whatever.
    // something that will be unique.
    // this method will only be called if it's not already in cache, and will
    // cache the result in the lru.
    getTheStatFromTheKey(key, cb)
  }
})

// then later..
stats.get(fd + ':' + path, function (er, stat) {
  // maybe loaded from cache, maybe just fetched
})
```

Except for the `load` method, all the options are passed unmolested to
the internal [lru-cache](http://npm.im/lru-cache).

### Differences from [lru-cache](http://npm.im/lru-cache)

Since values are fetched asynchronously, the `get` method takes a
callback, rather than returning the value synchronously.

While there is a `set(k,v)` method to manually seed the cache,
typically you'll just call `get` and let the load function fetch the
key for you.

Keys must uniquely identify a single object, and must contain all the
information required to fetch an object, and must be strings.

### Per key `maxAge`

If `load` callback is called with 3 arguments, the 3rd is passed to
the internal [lru-cache](http://npm.im/lru-cache) as a `maxAge` for
the retrieved key.

```javascript
  function load (key, cb) {
    getValueFromTheKey(key, function (err, item) {
      cb(err, item.value, item.maxAge)
    })
  }
```

## Methods

* `get(key, cb)` If the key is in the cache, then calls `cb(null,
  cached)` on nextTick.  Otherwise, calls the `load` function that was
  supplied in the options object.  If it doesn't return an error, then
  cache the result.  Multiple `get` calls with the same key will only
  ever have a single `load` call at the same time.

* `set(key, val, maxAge)` Seed the cache.  This doesn't have to be done, but
  can be convenient if you know that something will be fetched soon.
  `maxAge` is optional - it is passed to internal LRU cache

* `reset()` Drop all the items in the cache.
