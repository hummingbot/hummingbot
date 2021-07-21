<img
  src="https://contrast.now.sh/cff/40f?size=192&fontSize=2&baseline=2&fontWeight=900&radius=32&text=UI"
  width="96"
  heigh="96"
/>

# Theme UI

Build consistent, themeable React apps based on constraint-based design principles | Built with Emotion + Styled System + MDX + Typography.js

[![GitHub][github-badge]][github]
[![Stars][stars]][github]
[![Build Status][circleci-badge]][circleci]
[![Version][version]][npm]
![MIT License][license]
[![system-ui/theme][system-ui-badge]](https://system-ui.com/theme)
![][size]

https://theme-ui.com

[github]: https://github.com/system-ui/theme-ui
[github-badge]: https://flat.badgen.net/badge/-/github?icon=github&label
[stars]: https://flat.badgen.net/github/stars/system-ui/theme-ui
[circleci]: https://circleci.com/gh/system-ui/theme-ui
[circleci-badge]: https://flat.badgen.net/circleci/github/system-ui/theme-ui/master
[version]: https://flat.badgen.net/npm/v/theme-ui
[npm]: https://npmjs.com/package/theme-ui
[license]: https://flat.badgen.net/badge/license/MIT/blue
[system-ui-badge]: https://flat.badgen.net/badge/system-ui/theme/black
[size]: https://flat.badgen.net/bundlephobia/minzip/theme-ui

Built for white-labels, themes, and other applications where customizing colors, typography, and layout are treated as first-class citizens
and based on the System UI [Theme Specification][],
Theme UI is intended to work in a variety of applications, libraries, and other UI components.
Colors, typography, and layout styles derived from customizable scales and design tokens,
help you build UI rooted in constraint-based design principles.

- Styled system without creating components
- First class support for the `css` prop
- Style [MDX][] content with a simple, expressive API
- Use [Typography.js][] themes
- Works with virtually any UI component library
- Works with existing [Styled System][] components
- Quick mobile-first responsive styles
- Built-in support for dark modes
- Primitive page layout components
- Plugin for use in [Gatsby][] sites and themes
- Define your own design tokens
- Built with the System UI [Theme Specification][] for interoperability
- Keep styles isolated with [Emotion][]

[emotion]: https://emotion.sh
[mdx]: https://mdxjs.com
[styled system]: https://styled-system.com
[gatsby]: https://gatsbyjs.org
[@styled-system/css]: https://styled-system.com/css
[theme specification]: https://system-ui.com/theme
[typography.js]: https://github.com/KyleAMathews/typography.js

## Getting Started

```sh
npm i theme-ui @emotion/core @mdx-js/react
```

Any styles in your app can reference values from the global `theme` object.
To provide the theme in context,
wrap your application with the `ThemeProvider` component and pass in a custom `theme` object.

```jsx
// basic usage
import React from 'react'
import { ThemeProvider } from 'theme-ui'
import theme from './theme'

export default props => (
  <ThemeProvider theme={theme}>{props.children}</ThemeProvider>
)
```

The `theme` object follows the System UI [Theme Specification](/theme-spec),
which lets you define custom color palettes, typographic scales, fonts, and more.
Read more about [theming](https://theme-ui.com/theming).

```js
// example theme.js
export default {
  fonts: {
    body: 'system-ui, sans-serif',
    heading: '"Avenir Next", sans-serif',
    monospace: 'Menlo, monospace',
  },
  colors: {
    text: '#000',
    background: '#fff',
    primary: '#33e',
  },
}
```

## `sx` prop

The `sx` prop works similarly to Emotion's `css` prop, accepting style objects to add CSS directly to an element in JSX, but includes extra theme-aware functionality.
Using the `sx` prop for styles means that certain properties can reference values defined in your `theme` object.
This is intended to make keeping styles consistent throughout your app the easy thing to do.

The `sx` prop only works in modules that have defined a custom pragma at the top of the file, which replaces the default `React.createElement` function.
This means you can control which modules in your application opt into this feature without the need for a Babel plugin or additional configuration.

```jsx
/** @jsx jsx */
import { jsx } from 'theme-ui'

export default props => (
  <div
    sx={{
      fontWeight: 'bold',
      fontSize: 4, // picks up value from `theme.fontSizes[4]`
      color: 'primary', // picks up value from `theme.colors.primary`
    }}>
    Hello
  </div>
)
```

Under the hood, this uses the [`@styled-system/css`](https://styled-system.com/css) utility and Emotion's custom JSX pragma implementation.
Read more about [how the custom pragma works](https://theme-ui.com/how-it-works/#jsx-pragma).

## Responsive styles

The `sx` prop also supports using arrays as values to change properties responsively with a mobile-first approach.
This API originated in [Styled System][] and is intended as [a terser syntax for applying responsive styles](https://styled-system.com/guides/array-props) across a singular dimension.

```jsx
/** @jsx jsx */
import { jsx } from 'theme-ui'

export default props => (
  <div
    sx={{
      // applies width 100% to all viewport widths,
      // width 50% above the first breakpoint,
      // and 25% above the next breakpoint
      width: ['100%', '50%', '25%'],
    }}
  />
)
```

---

## Documentation

- [Theming](https://theme-ui.com/theming)
- [The `sx` Prop](https://theme-ui.com/sx-prop)
- [Layout](https://theme-ui.com/layout)
- [Color Modes](https://theme-ui.com/color-modes)
- [Styled](https://theme-ui.com/styled)
- [MDX Components](https://theme-ui.com/mdx-components)
- [Theme Spec](https://theme-ui.com/theme-spec)
- [Gatsby Plugin](https://theme-ui.com/gatsby-plugin)
- [API](https://theme-ui.com/api)

MIT License
