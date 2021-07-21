---
title: Getting Started
order: 1
---

This page will explain how to install the Wonka package and
its basic usage and helper functions.

## Installation

The `wonka` package from `npm` is all you need to install to use
Wonka. The process is the same with `yarn` and `esy`.

```bash
yarn add wonka
# or with npm:
npm install --save wonka
# or with esy:
esy add wonka
```

For **JavaScript projects**, the package contains both CommonJS and
ES Modules bundles. For Flow and TypeScript the package also contains
typings files already, so if you're using either you're already done and
ready to go.

If you're using **BuckleScript** or `bs-native` you will need to add `"wonka"`
to your `bs-dependencies` in your `bsconfig.json` configuration file:

```diff
{
  "name": "<some_name>",
  "version": "0.1.0",
  "sources": ["src"],
  "bsc-flags": ["-bs-super-errors"],
  "bs-dependencies": [
+   "wonka"
  ]
}
```

If you're using **Dune** and **Esy** you will need to add `wonka` to
your `libraries` entry in the respective `dune` configuration file:

```diff
(library
  (name some_name)
  (public_name some_name)
+ (libraries wonka)
)
```

## Usage with JavaScript

In most cases you'll simply import or require `wonka` and use its exposed
methods and utilities. In both CommonJS and ES Modules the Wonka package
simply exposes all its utilities.

```js
// With CommonJS
const { fromArray } = require('wonka');
// With ES Modules
import { fromArray } from 'wonka';
```

There are also some special operators in Wonka that will only be exposed in
Web/JavaScript environments, like `fromPromise`, `toPromise`,
or `fromEvent`, or even `debounce` and `throttle`.
In TypeScript and Flow the typings also expose all types.

There's also a special utility in JavaScript environments to replace the pipeline
operator. This function is called `pipe` and simply calls functions that it's
being passed in order with the previous return value.

```js
import { pipe } from 'wonka';

const output = pipe(
  'test',
  x => x + ' this',
  x => x.toUpperCase()
);

output; // "TEST THIS"
```

As shown above, the `pipe` function takes the first argument and passes it
in order to the other function arguments. The return value of one function will
be passed on to the next function.

In TypeScript and Flow the `pipe` function is also typed to handle all generics
in Wonka utilities correctly. Using it will ensure that most of the time you won't
have to specify the types of any generics manually.

If you're using Babel and the [pipeline proposal plugin](https://babeljs.io/docs/en/babel-plugin-proposal-pipeline-operator), you can just use
the pipeline operator to do the same and not use the `pipe` helper.

## Usage with Reason

Everything in the Wonka package is exposed under a single module called `Wonka`.
This module also contains `Wonka.Types`, which contains all internal types of the Wonka
library, but you will typically not need it.

In `BuckleScript` when you're compiling to JavaScript you will also have access to
more utilities like `fromPromise`, `toPromise`, `fromEvent`, or even `debounce` and `throttle`.
These utilities are missing in native compilation, like Dune or `bsb-native`, since they're
relying on JavaScript APIs like Promises, `window.addEventListener`, and `setTimeout`.

When using Wonka you'd simply either open the module and use its utilities or just
access them from the `Wonka` module:

```reason
Wonka.fromValue("test")
  |> Wonka.map((.x) => x ++ " this")
  |> Wonka.forEach((.x) => print_endline(x));
```

It's worth noting that most callbacks in Wonka need to be explicitly uncurried, since
this will help them compile cleanly to JavaScript.

## Interoperability

In JavaScript environments, Wonka comes with several utilities that make it easier
to interoperate with JavaScript primitives and other libraries:

- [`fromPromise`](./api/sources.md#frompromise) & [`toPromise`](./api/sinks.md#topromise) can be used to interoperate with Promises
- [`fromObservable`](./api/sources.md#fromobservable) & [`toObservable`](./api/sinks.md#toobservable) can be used to interoperate with spec-compliant Observables
- [`fromCallbag`](./api/sources.md#fromcallbag) & [`toCallbag`](./api/sinks.md#tocallbag) can be used to interoperate with spec-compliant Callbags

Furthermore there are a couple of operators that only work in JavaScript environments
since they need timing primitives, like `setTimeout` and `setInterval`:

- [`delay`](./api/operators.md#delay)
- [`debounce`](./api/operators.md#debounce)
- [`throttle`](./api/operators.md#throttle)
- [`interval`](./api/sources.md#interval)
