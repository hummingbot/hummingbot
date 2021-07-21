# `babel-plugin-extract-export-names`

Babel plugin that extracts all variable names from
export statements.Used by the [MDX](https://mdxjs.com)
pragma.

## Installation

```sh
yarn add babel-plugin-extract-export-names
```

## Usage

```js
const babel = require('@babel/core')

const BabelPluginExtractExportNames = require('babel-plugin-extract-export-names')

const jsx = `
export const foo = 'bar'
export const [A] = [1]
`

const plugin = new BabelPluginExtractExportNames()

const result = babel.transform(jsx, {
  configFile: false,
  plugins: [plugin.plugin]
})

console.log(plugin.state.names)
```

## License

MIT
