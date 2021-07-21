# DataLoader

DataLoader is a generic utility to be used as part of your application's data
fetching layer to provide a simplified and consistent API over various remote
data sources such as databases or web services via batching and caching.

[![Build Status](https://travis-ci.org/facebook/dataloader.svg)](https://travis-ci.org/facebook/dataloader)
[![Coverage Status](https://coveralls.io/repos/facebook/dataloader/badge.svg?branch=master&service=github)](https://coveralls.io/github/facebook/dataloader?branch=master)

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
var DataLoader = require('dataloader')

var userLoader = new DataLoader(keys => myBatchGetUsers(keys));
```

A batch loading function accepts an Array of keys, and returns a Promise which
resolves to an Array of values[<sup>*</sup>](#batch-function).

Then load individual values from the loader. DataLoader will coalesce all
individual loads which occur within a single frame of execution (a single tick
of the event loop) and then call your batch function with all requested keys.

```js
userLoader.load(1)
  .then(user => userLoader.load(user.invitedByID))
  .then(invitedBy => console.log(`User 1 was invited by ${invitedBy}`));

// Elsewhere in your application
userLoader.load(2)
  .then(user => userLoader.load(user.lastInvitedID))
  .then(lastInvited => console.log(`User 2 last invited ${lastInvited}`));
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
resolves to an Array of values. There are a few constraints that must be upheld:

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
  null,
  { id: 1, name: 'New York' }
]
```


## Caching

DataLoader provides a memoization cache for all loads which occur in a single
request to your application. After `.load()` is called once with a given key,
the resulting value is cached to eliminate redundant loads.

In addition to relieving pressure on your data storage, caching results per-request
also creates fewer objects which may relieve memory pressure on your application:

```js
var userLoader = new DataLoader(...)
var promise1A = userLoader.load(1)
var promise1B = userLoader.load(1)
assert(promise1A === promise1B)
```

#### Caching per-Request

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

var app = express()

app.get('/', function(req, res) {
  var authToken = authenticateUser(req)
  var loaders = createLoaders(authToken)
  res.send(renderPage(req, loaders))
})

app.listen()
```

#### Clearing Cache

In certain uncommon cases, clearing the request cache may be necessary.

The most common example when clearing the loader's cache is necessary is after
a mutation or update within the same request, when a cached value could be out of
date and future loads should not use any possibly cached value.

Here's a simple example using SQL UPDATE to illustrate.

```js
// Request begins...
var userLoader = new DataLoader(...)

// And a value happens to be loaded (and cached).
userLoader.load(4).then(...)

// A mutation occurs, invalidating what might be in cache.
sqlRun('UPDATE users WHERE id=4 SET username="zuck"').then(
  () => userLoader.clear(4)
)

// Later the value load is loaded again so the mutated data appears.
userLoader.load(4).then(...)

// Request completes.
```

#### Caching Errors

If a batch load fails (that is, a batch function throws or returns a rejected
Promise), then the requested values will not be cached. However if a batch
function returns an `Error` instance for an individual value, that `Error` will
be cached to avoid frequently loading the same `Error`.

In some circumstances you may wish to clear the cache for these individual Errors:

```js
userLoader.load(1).catch(error => {
  if (/* determine if should clear error */) {
    userLoader.clear(1);
  }
  throw error;
});
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
var myLoader = new DataLoader(keys => {
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
var myLoader = new DataLoader(keys => {
  identityLoader.clearAll()
  return someBatchLoadFn(keys)
})
```


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
  | *batch*  | Boolean | `true` | Set to `false` to disable batching, invoking `batchLoadFn` with a single load key.
  | *maxBatchSize* | Number | `Infinity` | Limits the number of items that get passed in to the `batchLoadFn`.
  | *cache* | Boolean | `true` | Set to `false` to disable memoization caching, creating a new Promise and new key in the `batchLoadFn` for every load of the same key. 
  | *cacheKeyFn* | Function | `key => key` | Produces cache key for a given load key. Useful when objects are keys and two objects should be considered equivalent.
  | *cacheMap* | Object | `new Map()` | Instance of [Map][] (or an object with a similar API) to be used as cache.

##### `load(key)`

Loads a key, returning a `Promise` for the value represented by that key.

- *key*: A key value to load.

##### `loadMany(keys)`

Loads multiple keys, promising an array of values:

```js
var [ a, b ] = await myLoader.loadMany([ 'a', 'b' ]);
```

This is equivalent to the more verbose:

```js
var [ a, b ] = await Promise.all([
  myLoader.load('a'),
  myLoader.load('b')
]);
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
var UserType = new GraphQLObjectType({
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
      resolve: (user, { first }) => queryLoader.load([
        'SELECT toID FROM friends WHERE fromID=? LIMIT ?', user.id, first
      ]).then(rows => rows.map(row => userLoader.load(row.toID)))
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
  };
}

// When handling an incoming web request:
var loaders = createLoaders(request.query.authToken);

// Then, within application logic:
var user = await loaders.users.load(4);
var pic = await loaders.cdnUrls.load(user.rawPicUrl);
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
let userByIDLoader = new DataLoader(ids => genUsersByID(ids).then(users => {
  for (let user of users) {
    usernameLoader.prime(user.username, user);
  }
  return users;
}));

let usernameLoader = new DataLoader(names => genUsernames(names).then(users => {
  for (let user of users) {
    userByIDLoader.prime(user.id, user);
  }
  return users;
}));
```


## Custom Caches

DataLoader can optionaly be provided a custom Map instance to use as its
memoization cache. More specifically, any object that implements the methods `get()`,
`set()`, `delete()` and `clear()` can be provided. This allows for custom Maps
which implement various [cache algorithms][] to be provided. By default,
DataLoader uses the standard [Map][] which simply grows until the DataLoader
is released. The default is appropriate when requests to your application are
short-lived.


## Common Back-ends

Looking to get started with a specific back-end? Try the [loaders in the examples directory](/examples).

## Other implementations

* PHP
  * [DataLoaderPHP](https://github.com/overblog/dataloader-php)
* Ruby
  * [Dataloader](https://github.com/sheerun/dataloader)
  * [BatchLoader](https://github.com/exaspark/batch-loader)
* ReasonML
  * [bs-dataloader](https://github.com/ulrikstrid/bs-dataloader)
* Java
  * [java-dataloader](https://github.com/graphql-java/java-dataloader)
* Elixir
  * [dataloader](https://github.com/absinthe-graphql/dataloader)
* Golang
  * [Dataloader](https://github.com/nicksrandall/dataloader)

## Video Source Code Walkthrough

**DataLoader Source Code Walkthrough (YouTube):**

<a href="https://youtu.be/OQTnXNCDywA" target="_blank" alt="DataLoader Source Code Walkthrough"><img src="https://img.youtube.com/vi/OQTnXNCDywA/0.jpg" /></a>


[@schrockn]: https://github.com/schrockn
[Map]: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Map
[graphql-js]: https://github.com/graphql/graphql-js
[cache algorithms]: https://en.wikipedia.org/wiki/Cache_algorithms
[express]: http://expressjs.com/
[babel/polyfill]: https://babeljs.io/docs/usage/polyfill/
