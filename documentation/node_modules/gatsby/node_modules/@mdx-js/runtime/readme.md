# `@mdx-js/runtime`

[![Build Status][build-badge]][build]
[![lerna][lerna-badge]][lerna]
[![Join the community on Spectrum][spectrum-badge]][spectrum]

Parse and render [MDX][] in a runtime environment.

> :warning: **warning**: this is not the preferred way to use MDX since it
> introduces a substantial amount of overhead and dramatically increases
> bundle sizes.
> It should also not be used with user input that isn’t sandboxed.

## Installation

[npm][]:

```sh
npm i -S @mdx-js/runtime
```

## Usage

```jsx
import React from 'react'
import MDX from '@mdx-js/runtime'

// Provide custom components for markdown elements
const components = {
  h1: props => <h1 style={{color: 'tomato'}} {...props} />,
  Demo: props => <h1>This is a demo component</h1>
}

// Provide variables that might be referenced by JSX
const scope = {
  some: 'value'
}

const mdx = `
# Hello, world!

<Demo />
`

export default () => (
  <MDX components={components} scope={scope}>
    {mdx}
  </MDX>
)
```

## Contribute

See the [Support][] and [Contributing][] guidelines on the MDX website for ways
to (get) help.

This project has a [Code of Conduct][coc].
By interacting with this repository, organisation, or community you agree to
abide by its terms.

## License

[MIT][] © [Compositor][] and [Vercel][]

[build]: https://travis-ci.com/mdx-js/mdx
[build-badge]: https://travis-ci.com/mdx-js/mdx.svg?branch=master
[lerna]: https://lernajs.io/
[lerna-badge]: https://img.shields.io/badge/maintained%20with-lerna-cc00ff.svg
[spectrum]: https://spectrum.chat/mdx
[spectrum-badge]: https://withspectrum.github.io/badge/badge.svg
[contributing]: https://mdxjs.com/contributing
[support]: https://mdxjs.com/support
[coc]: https://github.com/mdx-js/.github/blob/master/code-of-conduct.md
[mit]: license
[compositor]: https://compositor.io
[vercel]: https://vercel.com
[mdx]: https://github.com/mdx-js/mdx
[npm]: https://docs.npmjs.com/cli/install
