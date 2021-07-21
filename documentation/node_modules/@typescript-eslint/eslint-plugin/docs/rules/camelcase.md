# Enforce camelCase naming convention (`camelcase`)

## DEPRECATED

This rule has been deprecated in favour of the [`naming-convention`](./naming-convention.md) rule.
It will be removed in a future version of this plugin.

## Rule Details

This rule extends the base [`eslint/camelcase`](https://eslint.org/docs/rules/camelcase) rule.
It adds support for numerous TypeScript features.

## How to use

```jsonc
{
  // note you must disable the base rule as it can report incorrect errors
  "camelcase": "off",
  "@typescript-eslint/camelcase": ["error"]
}
```

## Options

See [`eslint/camelcase` options](https://eslint.org/docs/rules/camelcase#options).
This rule adds the following options:

```ts
interface Options extends BaseCamelcaseOptions {
  genericType?: 'always' | 'never';
}

const defaultOptions: Options = {
  ...baseCamelcaseDefaultOptions,
  genericType: 'never',
};
```

- `"genericType": "never"` (default) does not check generic identifiers
- `"genericType": "always"` enforces camelCase style for generic identifiers

### `genericType: "always"`

Examples of **incorrect** code for this rule with the default `{ "genericType": "always" }` option:

```typescript
/* eslint @typescript-eslint/camelcase: ["error", { "genericType": "always" }] */

interface Foo<t_foo> {}
function foo<t_foo>() {}
class Foo<t_foo> {}
type Foo<t_foo> = {};
class Foo {
  method<t_foo>() {}
}

interface Foo<t_foo extends object> {}
function foo<t_foo extends object>() {}
class Foo<t_foo extends object> {}
type Foo<t_foo extends object> = {};
class Foo {
  method<t_foo extends object>() {}
}

interface Foo<t_foo = object> {}
function foo<t_foo = object>() {}
class Foo<t_foo = object> {}
type Foo<t_foo = object> = {};
class Foo {
  method<t_foo = object>() {}
}
```

Examples of **correct** code for this rule with the default `{ "genericType": "always" }` option:

```typescript
/* eslint @typescript-eslint/camelcase: ["error", { "genericType": "always" }] */

interface Foo<T> {}
function foo<t>() {}
class Foo<T> {}
type Foo<T> = {};
class Foo {
  method<T>() {}
}

interface Foo<T extends object> {}
function foo<T extends object>() {}
class Foo<T extends object> {}
type Foo<T extends object> = {};
class Foo {
  method<T extends object>() {}
}

interface Foo<T = object> {}
function foo<T = object>() {}
class Foo<T = object> {}
type Foo<T = object> = {};
class Foo {
  method<T = object>() {}
}
```

### `genericType: "never"`

Examples of **correct** code for this rule with the `{ "genericType": "never" }` option:

```typescript
/* eslint @typescript-eslint/camelcase: ["error", { "genericType": "never" }] */

interface Foo<t_foo> {}
function foo<t_foo>() {}
class Foo<t_foo> {}
type Foo<t_foo> = {};
class Foo {
  method<t_foo>() {}
}

interface Foo<t_foo extends object> {}
function foo<t_foo extends object>() {}
class Foo<t_foo extends object> {}
type Foo<t_foo extends object> = {};
class Foo {
  method<t_foo extends object>() {}
}

interface Foo<t_foo = object> {}
function foo<t_foo = object>() {}
class Foo<t_foo = object> {}
type Foo<t_foo = object> = {};
class Foo {
  method<t_foo = object>() {}
}
```

<sup>Taken with ❤️ [from ESLint core](https://github.com/eslint/eslint/blob/master/docs/rules/camelcase.md)</sup>
