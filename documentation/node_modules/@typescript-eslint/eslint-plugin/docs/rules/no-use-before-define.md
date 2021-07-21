# Disallow the use of variables before they are defined (`no-use-before-define`)

## PLEASE READ THIS ISSUE BEFORE USING THIS RULE [#1856](https://github.com/typescript-eslint/typescript-eslint/issues/1856)

## Rule Details

This rule extends the base [`eslint/no-use-before-define`](https://eslint.org/docs/rules/no-use-before-define) rule.
It adds support for `type`, `interface` and `enum` declarations.

## How to use

```jsonc
{
  // note you must disable the base rule as it can report incorrect errors
  "no-use-before-define": "off",
  "@typescript-eslint/no-use-before-define": ["error"]
}
```

## Options

See [`eslint/no-use-before-define` options](https://eslint.org/docs/rules/no-use-before-define#options).
This rule adds the following options:

```ts
interface Options extends BaseNoMagicNumbersOptions {
  enums?: boolean;
  typedefs?: boolean;
}

const defaultOptions: Options = {
  ...baseNoMagicNumbersDefaultOptions,
  enums: true,
  typedefs: true,
};
```

### `enums`

The flag which shows whether or not this rule checks enum declarations of upper scopes.
If this is `true`, this rule warns every reference to a enum before the enum declaration.
Otherwise, ignores those references.

Examples of **incorrect** code for the `{ "enums": true }` option:

```ts
/*eslint no-use-before-define: ["error", { "enums": true }]*/

function foo() {
  return Foo.FOO;
}

class Test {
  foo() {
    return Foo.FOO;
  }
}

enum Foo {
  FOO,
  BAR,
}
```

Examples of **correct** code for the `{ "enums": false }` option:

```ts
/*eslint no-use-before-define: ["error", { "enums": false }]*/

function foo() {
  return Foo.FOO;
}

enum Foo {
  FOO,
}
```

### `typedefs`

The flag which shows whether or not this rule checks type declarations.
If this is `true`, this rule warns every reference to a type before the type declaration.
Otherwise, ignores those references.
Type declarations are hoisted, so it's safe.

Examples of **correct** code for the `{ "typedefs": false }` option:

```ts
/*eslint no-use-before-define: ["error", { "typedefs": false }]*/

let myVar: StringOrNumber;
type StringOrNumber = string | number;
```

Copied from [the original ESLint rule docs](https://github.com/eslint/eslint/blob/a113cd3/docs/rules/no-use-before-define.md)
