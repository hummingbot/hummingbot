---
title: Introduction
order: 0
---

Wonka is a lightweight iterable and observable library loosely based on
the [callbag spec](https://github.com/callbag/callbag). It exposes a set of helpers to create streams,
which are sources of multiple values, which allow you to create, transform
and consume event streams or iterable sets of data.

## What it is

Wonka is a library for streams _and_ iterables that behaves predictably
and can be used for many problems where you're dealing with streams of
values, asynchronous or not.

It's similar to [RxJS](https://github.com/ReactiveX/rxjs) in that it enables asynchronous programming with
observable streams, with an API that looks like functional programming on
iterables, but it's also similar to [IxJS](https://github.com/ReactiveX/IxJS) since Wonka streams will run
synchronously if an iterable source runs synchronously.

It also comes with many operators that users from [RxJS](https://github.com/ReactiveX/rxjs) will be used to.

## Compatibility

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

In summary, Wonka provides a consistent interface in and works across
TypeScript/Flow/Reason/OCaml environments with full type safety.

## About the docs

As mentioned in the prior section, Wonka supports not one but a couple of
environments and languages. To accommodate for this, most of the docs
are written with examples and sections for TypeScript and Reason.

We don't provide examples in most parts of the docs for Flow and OCaml because
their respective usage is almost identical to TypeScript and Reason, so for
the most part the examples mostly deal with the differences between a
TypeScript and a Reason project.
