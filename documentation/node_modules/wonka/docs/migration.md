---
title: Migration
order: 2
---

This page lists breaking changes and migration guides for
various major releases of Wonka.

## v4.0.0

In `v4.0.0` of Wonka, we've migrated to BuckleScript v7 and
`genType` for automatic type generation for TypeScript. The
Flow types are derived from the automatic types and are generated
by `flowgen`.

This may mean that `bsb-native` and Dune/Esy builds are temporarily
broken, as they haven't been tested yet. If so, they will be fixed
in a future minor release. Please stick with `v3.2.2` if you're having
trouble.

This release has no breaking changes for Reason/OCaml in terms of
API changes. You can use the library exactly as you have before.

**For TypeScript and Flow some APIs have changed**.

### New TypeScript and Flow typings

The type for `Subscription`, `Observer`, and `Subject` have changed.
These used to be exposed as tuples (fixed-size arrays) in the past,
but are now compiled to objects, due to the upgrade to BuckleScript v7.

If you're using `subscribe`, `makeSubject`, or `make` you will have
to change some of your types. If you don't, you won't have to update
any of your code and can even mix Wonka `v4.0.0` with `v3.2.2` in the
same bundle.

The `Subscription` type has changed from `[() => void]` to
`{ unsubscribe: (_: void) => void }`:

```ts
import { subscribe } from 'wonka';

// Before:
const [unsubscribe] = subscribe(source);
// After:
const { unsubscribe } = subscribe(source);
```

The `Observer` type has changed similarly, so you'll have to
update your code if you're using `make`:

```ts
import { make } from 'wonka';

// Before:
const source = make(([next, complete]) => /* ... */);
// After:
const source = make(({ next, complete }) => /* ... */);
```

And lastly the `Subject` type has changed as well, so update
your usage of `makeSubject`:

```ts
import { makeSubject } from 'wonka';

// Before:
const [source, next, complete] = makeSubject();
// After:
const { source, next, complete } = makeSubject();
```

### Improvements

The test suite has been rewritten from scratch to improve our
testing of some tricky edge cases. In most cases operators have
been updated to behave more nicely and closer to the spec and
as expected. This is especially true if you're using synchronous
sources or iterables a lot.

Wonka has reached a much higher test coverage and operators like
`merge` and `switchMap` will now behave as expected with synchronous
sources.

This is the list of operators that have changed. If your code has
been working before, you _shouldn't see any different behaviour_.
The changed operators will simply have received bugfixes and will
behave more predictably (and hopefully correctly) in certain edge cases!

- [`buffer`](./api/operators.md#buffer)
- [`combine`](./api/operators.md#combine)
- [`debounce`](./api/operators.md#debounce)
- [`delay`](./api/operators.md#delay)
- [`sample`](./api/operators.md#sample)
- [`skipUntil`](./api/operators.md#skipuntil)
- [`take`](./api/operators.md#take)
- [`takeLast`](./api/operators.md#takelast)
- [`takeWhile`](./api/operators.md#takewhile)
- [`switchMap`](./api/operators.md#switchmap)
- [`mergeMap`](./api/operators.md#mergemap)
- [`concatMap`](./api/operators.md#concatmap)
- [`switchAll`](./api/operators.md#switchall)
- [`mergeAll`](./api/operators.md#mergeall)
- [`concatAll`](./api/operators.md#concatall)
- [`merge`](./api/operators.md#merge)
- [`concat`](./api/operators.md#concat)

The `take` operator is the only one that has been changed to fix
a notable new usage case. It can now accept a maximum of `0` or below,
to close the source immediately.
