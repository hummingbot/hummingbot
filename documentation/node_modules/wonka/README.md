# Wonka

A fast push & pull stream library for Reason, loosely following the [callbag spec](https://github.com/callbag/callbag)

> **NOTE:** The `master` branch currently points to the v4 Release Candidate version!
> If you're looking for v3, [please check the `v3.2.2`](https://github.com/kitten/wonka/tree/v3.2.2)

<br>
<a href="https://npmjs.com/package/wonka">
  <img alt="NPM Version" src="https://img.shields.io/npm/v/wonka.svg" />
</a>
<a href="https://npmjs.com/package/wonka">
  <img alt="License" src="https://img.shields.io/npm/l/wonka.svg" />
</a>
<a href="https://coveralls.io/github/kitten/wonka?branch=master">
  <img src="https://coveralls.io/repos/github/kitten/wonka/badge.svg?branch=master" alt="Test Coverage" />
</a>
<a href="https://bundlephobia.com/result?p=wonka">
  <img alt="Minified gzip size" src="https://img.shields.io/bundlephobia/minzip/wonka.svg?label=gzip%20size" />
</a>
<br>

> “There’s no earthly way of knowing<br>
> Which direction we are going<br>
> There’s no knowing where we’re rowing<br>
> Or which way the river’s flowing” － **Willy Wonka**

<br>

![Wonka](/docs/wonka.jpg?raw=true)

Wonka is a lightweight iterable and observable library loosely based on
the [callbag spec](https://github.com/callbag/callbag). It exposes a set of helpers to create streams,
which are sources of multiple values, which allow you to create, transform
and consume event streams or iterable sets of data.

Wonka is written in [Reason](https://reasonml.github.io/), a dialect of OCaml, and can hence be used
for native applications. It is also compiled using [BuckleScript](https://bucklescript.github.io) to plain
JavaScript and has typings for [TypeScript](https://www.typescriptlang.org/) and [Flow](https://flow.org/).

This means that out of the box Wonka is usable in any project that use the following:

- Plain JavaScript
- TypeScript
- Flow
- Reason/OCaml with BuckleScript
- Reason/OCaml with `bs-native`
- Reason/OCaml with Dune and Esy

## [Documentation](https://wonka.kitten.sh/)

**See the documentation at [wonka.kitten.sh](https://wonka.kitten.sh)** for more information about using `wonka`!

- [Introduction](https://wonka.kitten.sh/)
- [**Getting started**](https://wonka.kitten.sh/getting-started)
- [Basics](https://wonka.kitten.sh/basics/)
- [API Reference](https://wonka.kitten.sh/api/)

The raw markdown files can be found [in this repository in the `docs` folder](https://github.com/kitten/wonka/tree/master/docs).
