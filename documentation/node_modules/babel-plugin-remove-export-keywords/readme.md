# `babel-plugin-remove-export-keywords`

Remove export keywords by coercing them into variable
declarations. Used by [MDX](https://mdxjs.com).

## Installation

```sh
yarn add babel-plugin-remove-export-keywords
```

## Usage

```js
const babel = require('@babel/core')

const plugin = require('babel-plugin-remove-export-keywords')

const jsx = `
export const Foo = () => (
  <div>
    <Button />
  </div>
)
`

const plugin = new BabelPluginApplyMdxTypeProp()

const result = babel.transform(jsx, {
  configFile: false,
  plugins: ['@babel/plugin-syntax-jsx', plugin]
})

console.log(result.code)
```

### Input

```js
export const Foo = () => (
  <div>
    <Button />
  </div>
)
```

### Output

```js
const Foo = () => (
  <div>
    <Button mdxType="Button" />
  </div>
)
```

## License

MIT
