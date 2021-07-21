# DataLoader

DataLoader is a generic utility to be used as part of your application's data
fetching layer to provide a simplified and consistent API over various remote
data sources such as databases or web services via batching and caching.

[![Build Status](https://travis-ci.org/graphql/dataloader.svg)](https://travis-ci.org/graphql/dataloader)
[![Coverage Status](https://coveralls.io/repos/graphql/dataloader/badge.svg?branch=master&service=github)](https://coveralls.io/github/graphql/dataloader?branch=master)

A port of the "Loader" API originally developed by [@schrockn][] at Facebook in
2010 as a simplifying force to coalesce the sundry key-value store back-end
APIs which existed at the time. At Facebook, "Loader" became one of the
implementation details of the "Ent" framework, a privacy-aware data entity
loading and caching layer within web server product code. This ultimately became
the underpinning for Facebook's GraphQL server implementation and type
definitions.

DataLoader is a simplified version of this original idea implemented in
JavaScript for Node.js services. DataLoader is often used when implementing a
[graphql-js][] service, though it is also broadly useful in other situations.

This mechanism of batching and caching data requests is certainly not unique to
Node.js or JavaScript, it is also the primary motivation for
[Haxl](https://github.com/facebook/Haxl), Facebook's data loading library
for Haskell. More about how Haxl works can be read in this [blog post](https://code.facebook.com/posts/302060973291128/open-sourcing-haxl-a-library-for-haskell/).

DataLoader is provided so that it may be useful not just to build GraphQL
services for Node.js but also as a publicly available reference implementation
of this concept in the hopes that it can be ported to other languages. If you
port DataLoader to another language, please open an issue to include a link from
this repository.


## Getting Started

First, install DataLoader using npm.

```sh
npm install --save dataloader
```

To get started, create a `DataLoader`. Each `DataLoader` instance represents a
unique cache. Typically instances are created per request when used within a
web-server like [express][] if different users can see different things.

> Note: DataLoader assumes a JavaScript environment with global ES6 `Promise`
and `Map` classes, available in all supported versions of Node.js.


## Batching

Batching is not an advanced feature, it's DataLoader's primary feature.
Create loaders by providing a batch loading function.

```js
const DataLoader = require('dataloader')

const userLoader = new DataLoader(keys => myBatchGetUsers(keys))
```

A batch loading function accepts an Array of keys, and returns a Promise which
resolves to an Array of values[<sup>*</sup>](#batch-function).

Then load individual values from the loader. DataLoader will coalesce all
individual loads which occur within a single frame of execution (a single tick
of the event loop) and then call your batch function with all requested keys.

```js
const user = await userLoader.load(1)
const invitedBy = await userLoader.load(user.invitedByID)
console.log(`User 1 was invited by ${invitedBy}`)

// Elsewhere in your application
const user = await userLoader.load(2)
const lastInvited = await userLoader.load(user.lastInvitedID)
console.log(`User 2 last invited ${lastInvited}`)
```

A naive application may have issued four round-trips to a backend for the
required information, but with DataLoader this application will make at most
two.

DataLoader allows you to decouple unrelated parts of your application without
sacrificing the performance of batch data-loading. While the loader presents an
API that loads individual values, all concurrent requests will be coalesced and
presented to your batch loading function. This allows your application to safely
distribute data fetching requirements throughout your application and maintain
minimal outgoing data requests.

#### Batch Function

A batch loading function accepts an Array of keys, and returns a Promise which
resolves to an Array of values or Error instances. The loader itself is provided
as the `this` context.

```js
async function batchFunction(keys) {
  const results = await db.fetchAllKeys(keys)
  return keys.map(key => results[key] || new Error(`No result for ${key}`))
}

const loader = new DataLoader(batchFunction)
```

There are a few constraints this function must uphold:

 * The Array of values must be the same length as the Array of keys.
 * Each index in the Array of values must correspond to the same index in the Array of keys.

For example, if your batch function was provided the Array of keys: `[ 2, 9, 6, 1 ]`,
and loading from a back-end service returned the values:

```js
{ id: 9, name: 'Chicago' }
{ id: 1, name: 'New York' }
{ id: 2, name: 'San Francisco' }
```

Our back-end service returned results in a different order than we requested, likely
because it was more efficient for it to do so. Also, it omitted a result for key `6`,
which we can interpret as no value existing for that key.

To uphold the constraints of the batch function, it must return an Array of values
the same length as the Array of keys, and re-order them to ensure each index aligns
with the original keys `[ 2, 9, 6, 1 ]`:

```js
[
  { id: 2, name: 'San Francisco' },
  { id: 9, name: 'Chicago' },
  null, // or perhaps `new Error()`
  { id: 1, name: 'New York' }
]
```

#### Batch Scheduling

By default DataLoader will coalesce all individual loads which occur within a
single frame of execution before calling your batch function with all requested
keys. This ensures no additional latency while capturing many related requests
into a single batch. In fact, this is the same behavior used in Facebook's
original PHP implementation in 2010. See `enqueuePostPromiseJob` in the
[source code][] for more details about how this works.

However sometimes this behavior is not desirable or optimal. Perhaps you expect
requests to be spread out over a few subsequent ticks because of an existing use
of `setTimeout`, or you just want manual control over dispatching regardless of
the run loop. DataLoader allows providing a custom batch scheduler to provide
these or any other behaviors.

A custom scheduler is provided as `batchScheduleFn` in options. It must be a
function which is passed a callback and is expected to call that callback in the
immediate future to execute the batch request.

As an example, here is a batch scheduler which collects all requests over a
100ms window of time (and as a consequence, adds 100ms of latency):

```js
const myLoader = new DataLoader(myBatchFn, {
  batchScheduleFn: callback => setTimeout(callback, 100)
})
```

As another example, here is a manually dispatched batch scheduler:

```js
function createScheduler() {
  let callbacks = []
  return {
    schedule(callback) {
      callbacks.push(callback)
    },
    dispatch() {
      callbacks.forEach(callback => callback())
      callbacks = []
    }
  }
}

const { schedule, dispatch } = createScheduler()
const myLoader = new DataLoader(myBatchFn, { batchScheduleFn: schedule })

myLoader.load(1)
myLoader.load(2)
dispatch()
```


## Caching

DataLoader provides a memoization cache for all loads which occur in a single
request to your application. After `.load()` is called once with a given key,
the resulting value is cached to eliminate redundant loads.

#### Caching Per-Request

DataLoader caching *does not* replace Redis, Memcache, or any other shared
application-level cache. DataLoader is first and foremost a data loading mechanism,
and its cache only serves the purpose of not repeatedly loading the same data in
the context of a single request to your Application. To do this, it maintains a
simple in-memory memoization cache (more accurately: `.load()` is a memoized function).

Avoid multiple requests from different users using the DataLoader instance, which
could result in cached data incorrectly appearing in each request. Typically,
DataLoader instances are created when a Request begins, and are not used once the
Request ends.

For example, when using with [express][]:

```js
function createLoaders(authToken) {
  return {
    users: new DataLoader(ids => genUsers(authToken, ids)),
  }
}

const app = express()

app.get('/', function(req, res) {
  const authToken = authenticateUser(req)
  const loaders = createLoaders(authToken)
  res.send(renderPage(req, loaders))
})

app.listen()
```

#### Caching and Batching

Subsequent calls to `.load()` with the same key will result in that key not
appearing in the keys provided to your batch function. *However*, the resulting
Promise will still wait on the current batch to complete. This way both cached
and uncached requests will resolve at the same time, allowing DataLoader
optimizations for subsequent dependent loads.

In the example below, User `1` happens to be cached. However, because User `1`
and `2` are loaded in the same tick, they will resolve at the same time. This
means both `user.bestFriendID` loads will also happen in the same tick which
results in two total requests (the same as if User `1` had not been cached).

```js
userLoader.prime(1, { bestFriend: 3 })

async function getBestFriend(userID) {
  const user = await userLoader.load(userID)
  return await userLoader.load(user.bestFriendID)
}

// In one part of your application
getBestFriend(1)

// Elsewhere
getBestFriend(2)
```

Without this optimization, if the cached User `1` resolved immediately, this
could result in three total requests since each `user.bestFriendID` load would
happen at different times.

#### Clearing Cache

In certain uncommon cases, clearing the request cache may be necessary.

The most common example when clearing the loader's cache is necessary is after
a mutation or update within the same request, when a cached value could be out of
date and future loads should not use any possibly cached value.

Here's a simple example using SQL UPDATE to illustrate.

```js
// Request begins...
const userLoader = new DataLoader(...)

// And a value happens to be loaded (and cached).
const user = await userLoader.load(4)

// A mutation occurs, invalidating what might be in cache.
await sqlRun('UPDATE users WHERE id=4 SET username="zuck"')
userLoader.clear(4)

// Later the value load is loaded again so the mutated data appears.
const user = await userLoader.load(4)

// Request completes.
```

#### Caching Errors

If a batch load fails (that is, a batch function throws or returns a rejected
Promise), then the requested values will not be cached. However if a batch
function returns an `Error` instance for an individual value, that `Error` will
be cached to avoid frequently loading the same `Error`.

In some circumstances you may wish to clear the cache for these individual Errors:

```js
try {
  const user = await userLoader.load(1)
} catch (error) {
  if (/* determine if the error should not be cached */) {
    userLoader.clear(1)
  }
  throw error
}
```

#### Disabling Cache

In certain uncommon cases, a DataLoader which *does not* cache may be desirable.
Calling `new DataLoader(myBatchFn, { cache: false })` will ensure that every
call to `.load()` will produce a *new* Promise, and requested keys will not be
saved in memory.

However, when the memoization cache is disabled, your batch function will
receive an array of keys which may contain duplicates! Each key will be
associated with each call to `.load()`. Your batch loader should provide a value
for each instance of the requested key.

For example:

```js
const myLoader = new DataLoader(keys => {
  console.log(keys)
  return someBatchLoadFn(keys)
}, { cache: false })

myLoader.load('A')
myLoader.load('B')
myLoader.load('A')

// > [ 'A', 'B', 'A' ]
```

More complex cache behavior can be achieved by calling `.clear()` or `.clearAll()`
rather than disabling the cache completely. For example, this DataLoader will
provide unique keys to a batch function due to the memoization cache being
enabled, but will immediately clear its cache when the batch function is called
so later requests will load new values.

```js
const myLoader = new DataLoader(keys => {
  identityLoader.clearAll()
  return someBatchLoadFn(keys)
})
```

#### Custom Cache

As mentioned above, DataLoader is intended to be used as a per-request cache.
Since requests are short-lived, DataLoader uses an infinitely growing [Map][] as
a memoization cache. This should not pose a problem as most requests are
short-lived and the entire cache can be discarded after the request completes.

However this memoization caching strategy isn't safe when using a long-lived
DataLoader, since it could consume too much memory. If using DataLoader in this
way, you can provide a custom Cache instance with whatever behavior you prefer,
as long as it follows the same API as [Map][].

The example below uses an LRU (least recently used) cache to limit total memory
to hold at most 100 cached values via the [lru_map][] npm package.

```js
import { LRUMap } from 'lru_map'

const myLoader = new DataLoader(someBatchLoadFn, {
  cacheMap: new LRUMap(100)
})
```

More specifically, any object that implements the methods `get()`, `set()`,
`delete()` and `clear()` methods can be provided. This allows for custom Maps
which implement various [cache algorithms][] to be provided.


## API

#### class DataLoader

DataLoader creates a public API for loading data from a particular
data back-end with unique keys such as the `id` column of a SQL table or
document name in a MongoDB database, given a batch loading function.

Each `DataLoader` instance contains a unique memoized cache. Use caution when
used in long-lived applications or those which serve many users with different
access permissions and consider creating a new instance per web request.

##### `new DataLoader(batchLoadFn [, options])`

Create a new `DataLoader` given a batch loading function and options.

- *batchLoadFn*: A function which accepts an Array of keys, and returns a
  Promise which resolves to an Array of values.

- *options*: An optional object of options:

  | Option Key | Type | Default | Description |
  | ---------- | ---- | ------- | ----------- |
  | *batch*  | Boolean | `true` | Set to `false` to disable batching, invoking `batchLoadFn` with a single load key. This is equivalent to setting `maxBatchSize` to `1`.
  | *maxBatchSize* | Number | `Infinity` | Limits the number of items that get passed in to the `batchLoadFn`. May be set to `1` to disable batching.
  | *batchScheduleFn* | Function | See [Batch scheduling](#batch-scheduling) | A function to schedule the later execution of a batch. The function is expected to call the provided callback in the immediate future.
  | *cache* | Boolean | `true` | Set to `false` to disable memoization caching, creating a new Promise and new key in the `batchLoadFn` for every load of the same key. This is equivalent to setting `cacheMap` to `null`.
  | *cacheKeyFn* | Function | `key => key` | Produces cache key for a given load key. Useful when objects are keys and two objects should be considered equivalent.
  | *cacheMap* | Object | `new Map()` | Instance of [Map][] (or an object with a similar API) to be used as cache. May be set to `null` to disable caching.

##### `load(key)`

Loads a key, returning a `Promise` for the value represented by that key.

- *key*: A key value to load.

##### `loadMany(keys)`

Loads multiple keys, promising an array of values:

```js
const [ a, b ] = await myLoader.loadMany([ 'a', 'b' ])
```

This is similar to the more verbose:

```js
const [ a, b ] = await Promise.all([
  myLoader.load('a'),
  myLoader.load('b')
])
```

However it is different in the case where any load fails. Where
Promise.all() would reject, loadMany() always resolves, however each result
is either a value or an Error instance.

```js
var [ a, b, c ] = await myLoader.loadMany([ 'a', 'b', 'badkey' ]);
// c instanceof Error
```

- *keys*: An array of key values to load.

##### `clear(key)`

Clears the value at `key` from the cache, if it exists. Returns itself for
method chaining.

- *key*: A key value to clear.

##### `clearAll()`

Clears the entire cache. To be used when some event results in unknown
invalidations across this particular `DataLoader`. Returns itself for
method chaining.

##### `prime(key, value)`

Primes the cache with the provided key and value. If the key already exists, no
change is made. (To forcefully prime the cache, clear the key first with
`loader.clear(key).prime(key, value)`.) Returns itself for method chaining.

To prime the cache with an error at a key, provide an Error instance.

## Using with GraphQL

DataLoader pairs nicely well with [GraphQL][graphql-js]. GraphQL fields are
designed to be stand-alone functions. Without a caching or batching mechanism,
it's easy for a naive GraphQL server to issue new database requests each time a
field is resolved.

Consider the following GraphQL request:

```
{
  me {
    name
    bestFriend {
      name
    }
    friends(first: 5) {
      name
      bestFriend {
        name
      }
    }
  }
}
```

Naively, if `me`, `bestFriend` and `friends` each need to request the backend,
there could be at most 13 database requests!

When using DataLoader, we could define the `User` type using the
[SQLite](examples/SQL.md) example with clearer code and at most 4 database requests,
and possibly fewer if there are cache hits.

```js
const UserType = new GraphQLObjectType({
  name: 'User',
  fields: () => ({
    name: { type: GraphQLString },
    bestFriend: {
      type: UserType,
      resolve: user => userLoader.load(user.bestFriendID)
    },
    friends: {
      args: {
        first: { type: GraphQLInt }
      },
      type: new GraphQLList(UserType),
      resolve: async (user, { first }) => {
        const rows = await queryLoader.load([
          'SELECT toID FROM friends WHERE fromID=? LIMIT ?', user.id, first
        ])
        return rows.map(row => userLoader.load(row.toID))
      }
    }
  })
})
```


## Common Patterns

### Creating a new DataLoader per request.

In many applications, a web server using DataLoader serves requests to many
different users with different access permissions. It may be dangerous to use
one cache across many users, and is encouraged to create a new DataLoader
per request:

```js
function createLoaders(authToken) {
  return {
    users: new DataLoader(ids => genUsers(authToken, ids)),
    cdnUrls: new DataLoader(rawUrls => genCdnUrls(authToken, rawUrls)),
    stories: new DataLoader(keys => genStories(authToken, keys)),
  }
}

// When handling an incoming web request:
const loaders = createLoaders(request.query.authToken)

// Then, within application logic:
const user = await loaders.users.load(4)
const pic = await loaders.cdnUrls.load(user.rawPicUrl)
```

Creating an object where each key is a `DataLoader` is one common pattern which
provides a single value to pass around to code which needs to perform
data loading, such as part of the `rootValue` in a [graphql-js][] request.

### Loading by alternative keys.

Occasionally, some kind of value can be accessed in multiple ways. For example,
perhaps a "User" type can be loaded not only by an "id" but also by a "username"
value. If the same user is loaded by both keys, then it may be useful to fill
both caches when a user is loaded from either source:

```js
const userByIDLoader = new DataLoader(async ids => {
  const users = await genUsersByID(ids)
  for (let user of users) {
    usernameLoader.prime(user.username, user)
  }
  return users
})

const usernameLoader = new DataLoader(async names => {
  const users = await genUsernames(names)
  for (let user of users) {
    userByIDLoader.prime(user.id, user)
  }
  return users
})
```

### Freezing results to enforce immutability

Since DataLoader caches values, it's typically assumed these values will be
treated as if they were immutable. While DataLoader itself doesn't enforce
this, you can create a higher-order function to enforce immutability
with Object.freeze():

```js
function freezeResults(batchLoader) {
  return keys => batchLoader(keys).then(values => values.map(Object.freeze))
}

const myLoader = new DataLoader(freezeResults(myBatchLoader))
```

### Batch functions which return Objects instead of Arrays

DataLoader expects batch functions which return an Array of the same length as
the provided keys. However this is not always a common return format from other
libraries. A DataLoader higher-order function can convert from one format to another. The example below converts a `{ key: value }` result to the format
DataLoader expects.

```js
function objResults(batchLoader) {
  return keys => batchLoader(keys).then(objValues => keys.map(
    key => objValues[key] || new Error(`No value for ${key}`)
  ))
}

const myLoader = new DataLoader(objResults(myBatchLoader))
```


## Common Back-ends

Looking to get started with a specific back-end? Try the [loaders in the examples directory](/examples).

## Other Implementations

Listed in alphabetical order

* Elixir
  * [dataloader](https://github.com/absinthe-graphql/dataloader)
* Golang
  * [Dataloader](https://github.com/nicksrandall/dataloader)
* Java
  * [java-dataloader](https://github.com/graphql-java/java-dataloader)
* .Net
  * [GraphQL .NET DataLoader](https://graphql-dotnet.github.io/docs/guides/dataloader/)
  * [GreenDonut](https://github.com/ChilliCream/greendonut)
* Perl
  * [perl-DataLoader](https://github.com/richardjharris/perl-DataLoader)
* PHP
  * [DataLoaderPHP](https://github.com/overblog/dataloader-php)
* Python
  * [aiodataloader](https://github.com/syrusakbary/aiodataloader)
* ReasonML
  * [bs-dataloader](https://github.com/ulrikstrid/bs-dataloader)
* Ruby
  * [BatchLoader](https://github.com/exaspark/batch-loader)
  * [Dataloader](https://github.com/sheerun/dataloader)
  * [GraphQL Batch](https://github.com/Shopify/graphql-batch)
* Rust
  * [Dataloader](https://github.com/cksac/dataloader-rs)
* Swift
  * [SwiftDataLoader](https://github.com/kimdv/SwiftDataLoader)

## Video Source Code Walkthrough

**DataLoader Source Code Walkthrough (YouTube):**

A walkthrough of the DataLoader v1 source code. While the source has changed
since this video was made, it is still a good overview of the rationale of
DataLoader and how it works.

<a href="https://youtu.be/OQTnXNCDywA" target="_blank" alt="DataLoader Source Code Walkthrough"><img src="https://img.youtube.com/vi/OQTnXNCDywA/0.jpg" /></a>


[@schrockn]: https://github.com/schrockn
[Map]: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Map
[graphql-js]: https://github.com/graphql/graphql-js
[cache algorithms]: https://en.wikipedia.org/wiki/Cache_algorithms
[express]: http://expressjs.com/
[babel/polyfill]: https://babeljs.io/docs/usage/polyfill/
[lru_map]: https://github.com/rsms/js-lru
[source code]: https://github.com/graphql/dataloader/blob/master/src/index.js
