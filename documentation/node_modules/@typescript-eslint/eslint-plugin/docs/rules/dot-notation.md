# enforce dot notation whenever possible (`dot-notation`)

## Rule Details

This rule extends the base [`eslint/dot-notation`](https://eslint.org/docs/rules/dot-notation) rule.
It adds support for optionally ignoring computed `private` member access.

## How to use

```cjson
{
  // note you must disable the base rule as it can report incorrect errors
  "dot-notation": "off",
  "@typescript-eslint/dot-notation": ["error"]
}
```

## Options

See [`eslint/dot-notation`](https://eslint.org/docs/rules/dot-notation#options) options.
This rule adds the following options:

```ts
interface Options extends BaseDotNotationOptions {
  allowPrivateClassPropertyAccess?: boolean;
}
const defaultOptions: Options = {
  ...baseDotNotationDefaultOptions,
  allowPrivateClassPropertyAccess: false,
};
```

### `allowPrivateClassPropertyAccess`

Example of a correct code when `allowPrivateClassPropertyAccess` is set to `true`

```ts
class X {
  private priv_prop = 123;
}

const x = new X();
x['priv_prop'] = 123;
```

<sup>Taken with ❤️ [from ESLint core](https://github.com/eslint/eslint/blob/master/docs/rules/dot-notation.md)</sup>
