# Disallow untyped public methods (`no-untyped-public-signature`)

public methods are meant to be used by code outside of your class. By typing both the parameters and the return type of public methods they will be more readable and easy to use.

## DEPRECATED

This rule has been deprecated in favour of the [`explicit-module-boundary-types`](./explicit-module-boundary-types.md) rule.
It will be removed in a future version of this plugin.

## Rule Details

This rule aims to ensure that only typed public methods are declared in the code.

The following patterns are considered warnings:

```ts
// untyped parameter
public foo(param1): void {
}

// untyped parameter
public foo(param1: any): void {
}

// untyped return type
public foo(param1: string) {
}

// untyped return type
public foo(param1: string): any {
}
```

The following patterns are not warnings:

```ts
// typed public method
public foo(param1: string): void {
}

// untyped private method
private foo(param1) {
}
```

## Options

This rule, in its default state, does not require any argument.

### `ignoredMethods`

You may pass method names you would like this rule to ignore, like so:

```jsonc
{
  "@typescript-eslint/no-untyped-public-signature": [
    "error",
    { "ignoredMethods": ["ignoredMethodName"] }
  ]
}
```

## When Not To Use It

If you don't wish to type public methods.
