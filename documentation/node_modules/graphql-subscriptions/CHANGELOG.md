# Changelog

### 1.1.0

- Fix [#132](https://github.com/apollographql/graphql-subscriptions/issues/132) - withFilter was previously always passing undefined as its first argument to the filterFn
- Partially attempt to fix [#143](https://github.com/apollographql/graphql-subscriptions/issues/143) - try to reduce occurrence of certain memory leaks with the built-in PubSubEngine implementation
- Replaced `eventEmitterAsyncIterator` with default generic `AsyncIterator` named `PubSubAsyncIterator`. `extends PubSubEngine` automatically uses generic implementation. No breaking changes for those who continue to use `implements PubSubEngine`. See PR [#78](https://github.com/apollographql/graphql-subscriptions/pull/78).

### 1.0.0

- BREAKING CHANGE: Changed return type of `publish`.  <br/>
  [@grantwwu](https://github.com/grantwwu) in [#162](https://github.com/apollographql/graphql-subscriptions/pull/162)
- Bump versions of various devDependencies to fix security issues, use
  newer tslint config.  <br/>
  [@grantwwu](https://github.com/grantwwu) in [#163](https://github.com/apollographql/graphql-subscriptions/pull/163)
- Allows `graphql` 14 as a peer dep, forces `graphql` 14 as a dev dep, and
  has been updated to use `@types/graphql` 14.  <br/>
  [@hwillson](https://github.com/hwillson) in [#172](https://github.com/apollographql/graphql-subscriptions/pull/172)

### 0.5.8
- Bump iterall version

### 0.5.7
- Add `graphql@0.13` to `peerDependencies`.

### 0.5.6
- Add `graphql@0.12` to `peerDependencies`.

### 0.5.5
- FilterFn can return a Promise<boolean>
- Allow passing in a custom `EventEmitter` to `PubSub`

### 0.5.4
- Better define `withFilter` return type [PR #111](https://github.com/apollographql/graphql-subscriptions/pull/111)

### 0.5.3
- Require iterall ^1.1.3 to address unhandled exceptions

### 0.5.2
- Require iterall ^1.1.2 to address memory leak [Issue #97] (https://github.com/apollographql/graphql-subscriptions/issues/97)
- Remove `@types/graphql` dependency. [PR #105] (https://github.com/apollographql/graphql-subscriptions/pull/105)

### 0.5.1
- `withFilter` now called with `(rootValue, args, context, info)` [PR #103] (https://github.com/apollographql/graphql-subscriptions/pull/103)

### 0.5.0
- BREAKING CHANGE: Removed deprecated code. [PR #104] (https://github.com/apollographql/graphql-subscriptions/pull/104)
- BREAKING CHANGE: Minimum GraphQL version bumped to 0.10.X. [PR #104] (https://github.com/apollographql/graphql-subscriptions/pull/104)

### 0.4.4
- Avoid infinite loop after the last consumer unsubscribes, [Issue #81](https://github.com/apollographql/graphql-subscriptions/issues/81) [PR #84](https://github.com/apollographql/graphql-subscriptions/pull/84)

### 0.4.3
- Properly propagate return() and throw() through withFilter [PR #74](https://github.com/apollographql/graphql-subscriptions/pull/74)

### 0.4.2
- Fixed issue with `withFilter` causing to use the same iterator [PR #69](https://github.com/apollographql/graphql-subscriptions/pull/69)

### 0.4.1
- Fixed exports issue with TypeScript [PR #65](https://github.com/apollographql/graphql-subscriptions/pull/65)

### 0.4.0
- Added `asyncIterator(channelName: string)` to `PubSub` implementation [PR #60](https://github.com/apollographql/graphql-subscriptions/pull/60)
- Added `withFilter` to allow `AsyncIterator` filtering [PR #60](https://github.com/apollographql/graphql-subscriptions/pull/60)
- Deprecate `SubscriptionManager` [PR #60](https://github.com/apollographql/graphql-subscriptions/pull/60)
- Fixed `withFilter` issue caused multiple subscribers to execute with the same AsyncIterator [PR #69](https://github.com/apollographql/graphql-subscriptions/pull/69)

### 0.3.1
- Add support for `defaultValue`, fixes [#49](https://github.com/apollographql/graphql-subscriptions/issues/49) (https://github.com/apollographql/graphql-subscriptions/pull/50)

### 0.3.0
- Allow `setupFunctions` to be async (return `Promise`) (https://github.com/apollographql/graphql-subscriptions/pull/41)
- Refactor promise chaining in pubsub engine (https://github.com/apollographql/graphql-subscriptions/pull/41)
- Fixed a possible bug with managing subscriptions internally (https://github.com/apollographql/graphql-subscriptions/pull/29)
- Return the `Promise` from `onMessage` of PubSub engine (https://github.com/apollographql/graphql-subscriptions/pull/33)

### 0.2.3
- update `graphql` dependency to 0.9.0

### 0.2.2
- made `graphql` a peer dependency and updated it to 0.8.2

### v 0.2.1
- Fixed a bug that caused subscriptions without operationName to fail
