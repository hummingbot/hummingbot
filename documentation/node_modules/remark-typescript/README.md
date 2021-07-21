# remark-typescript

[![Build Status](https://github.com/trevorblades/remark-typescript/workflows/Node%20CI/badge.svg)](https://github.com/trevorblades/remark-typescript/actions)

A [remark](https://github.com/remarkjs/remark) plugin to transpile TypeScript code blocks.

- [Installation](#installation)
- [Usage](#usage)
  - [Gatsby example](#gatsby-example)
- [API](#api)
  - [remark().use(remarkTypescript[, options])](#remarkuseremarktypescript-options)
- [Preserving unused imports](#preserving-unused-imports)
- [License](#license)

## Installation

```bash
npm install remark-typescript
```

## Usage

```js
import remark from 'remark';
import remarkTypescript from 'remark-typescript';

remark()
  .use(remarkTypescript)
  .process(...);
```

### Gatsby example

```js
// gatsby-config.js
const remarkTypescript = require('remark-typescript');

module.exports = {
  plugins: [
    {
      resolve: 'gatsby-plugin-mdx',
      options: {
        remarkPlugins: [remarkTypescript]
      }
    }
  ]
}
```

## API

### `remark().use(remarkTypescript[, options])`

Transform TypeScript code blocks to JavaScript and inserts them back into the page. Use `options` to affect the formatting or control which code blocks get transpiled.

#### `options.prettierOptions`

An object of options supplied to `prettier.format` when formatting the JS output. See [Prettier's docs](https://prettier.io/docs/en/options) for more information.

```js
import remark from 'remark';
import typescript from 'remark-typescript';

remark()
  .use(
    typescript,
    {
      prettierOptions: {
        semi: false,
        singleQuote: false
      }
    }
  )
  .process(...);
```

#### `options.wrapperComponent` (MDX only)

A string representing the name of the React component used to wrap code blocks that you wish to transform.

By default, `remark-typescript` will visit *all* TypeScript code blocks in your site and insert the transformed and formatted JavaScript after each of them. This feature allows the author to choose which TypeScript code blocks to transform by wrapping them in some JSX.

```js
// gatsby-config.js
const remarkTypescript = require('remark-typescript');

module.exports = {
  plugins: [
    {
      resolve: 'gatsby-plugin-mdx',
      options: {
        remarkPlugins: [
          [
            remarkTypescript,
            {
              // configure the JSX component that the plugin should check for
              wrapperComponent: 'CodeBlockWrapper'
            }
          ]
        ]
      }
    }
  ]
};
```

In your MDX file, surround code blocks that you want to be transformed with their own pair of opening and closing JSX tags. The name of the component that you use here must match the `wrapperComponent` option that you passed along to this plugin.

````jsx
import {CodeBlockWrapper} from '../components';

<CodeBlockWrapper>

```ts
// this code block will be transformed
```

</CodeBlockWrapper>

```ts
// this one will be ignored
```
````

Your wrapper component could include some additional logic, like allowing users to switch between the original and transformed code blocks. Check out Apollo's [`MultiCodeBlock` component](https://github.com/apollographql/gatsby-theme-apollo/blob/master/packages/gatsby-theme-apollo-docs/src/components/multi-code-block.js) for an example of how to accomplish this.

![Example wrapper component](./example.gif)

## Preserving unused imports

This plugin uses [Babel](https://babeljs.io) to do the transpilation, and because of this, you might notice unused imports being removed from your transpiled JavaScript codeblocks. To avoid this behavior, you can use a `// preserve-line` directive on lines that you don't want to be removed from the transpiled version.

````markdown
```ts
import gql from 'graphql-tag';
import {ApolloClient} from 'apollo-client'; // preserve-line

export const typeDefs = gql`
  type Query {
    posts: [Post]
  }
`;
```
````

## License

[MIT](./LICENSE)
