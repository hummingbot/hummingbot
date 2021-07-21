# Enforces consistent returning of awaited values (`return-await`)

Returning an awaited promise can make sense for better stack trace information as well as for consistent error handling (returned promises will not be caught in an async function try/catch).

## Rule Details

This rule builds on top of the [`eslint/no-return-await`](https://eslint.org/docs/rules/no-return-await) rule.
It expands upon the base rule to add support for optionally requiring `return await` in certain cases.

## How to use

```jsonc
{
  // note you must disable the base rule as it can report incorrect errors
  "no-return-await": "off",
  "@typescript-eslint/return-await": "error"
}
```

## Options

```ts
type Options = 'in-try-catch' | 'always' | 'never';

const defaultOptions: Options = 'in-try-catch';
```

### `in-try-catch`

Requires that a returned promise must be `await`ed in `try-catch-finally` blocks, and disallows it elsewhere.

Examples of **incorrect** code with `in-try-catch`:

```ts
async function invalidInTryCatch1() {
  try {
    return Promise.resolve('try');
  } catch (e) {}
}

async function invalidInTryCatch2() {
  return await Promise.resolve('try');
}

async function invalidInTryCatch3() {
  return await 'value';
}
```

Examples of **correct** code with `in-try-catch`:

```ts
async function validInTryCatch1() {
  try {
    return await Promise.resolve('try');
  } catch (e) {}
}

async function validInTryCatch2() {
  return Promise.resolve('try');
}

async function validInTryCatch3() {
  return 'value';
}
```

### `always`

Requires that all returned promises are `await`ed.

Examples of **incorrect** code with `always`:

```ts
async function invalidAlways1() {
  try {
    return Promise.resolve('try');
  } catch (e) {}
}

async function invalidAlways2() {
  return Promise.resolve('try');
}

async function invalidAlways3() {
  return await 'value';
}
```

Examples of **correct** code with `always`:

```ts
async function validAlways1() {
  try {
    return await Promise.resolve('try');
  } catch (e) {}
}

async function validAlways2() {
  return await Promise.resolve('try');
}

async function validAlways3() {
  return 'value';
}
```

### `never`

Disallows all `await`ing any returned promises.

Examples of **incorrect** code with `never`:

```ts
async function invalidNever1() {
  try {
    return await Promise.resolve('try');
  } catch (e) {}
}

async function invalidNever2() {
  return await Promise.resolve('try');
}

async function invalidNever3() {
  return await 'value';
}
```

Examples of **correct** code with `never`:

```ts
async function validNever1() {
  try {
    return Promise.resolve('try');
  } catch (e) {}
}

async function validNever2() {
  return Promise.resolve('try');
}

async function validNever3() {
  return 'value';
}
```
