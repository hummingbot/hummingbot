
# @styled-system/css

Styled System for the `css` prop

```sh
npm i @styled-system/css
```

Styled System CSS lets you write style objects with responsive, theme-aware Styled System shortcuts.

```jsx
// usage with the css prop
import React from 'react'
import css from '@styled-system/css'

const Beep = props =>
  <div
    {...props}
    css={css({
      fontSize: [4, 5, 6],
      color: 'primary',
    })}
  />
```

```js
// usage with a styled HOC
import styled from '@emotion/styled'
import css from '@styled-system/css'

const Boop = styled('div')(
  css({
    fontSize: [ 4, 5, 6 ],
    color: 'primary',
    bg: 'gray',
    '&:hover': {
      color: 'secondary',
    },
  })
)
```

To make the css prop work with `styled-components`, `babel-plugin-styled-components` must be enabled.

## Theme Keys

The following keys in your style object will work the same as Styled System props, pulling values from your `theme` object.

Property  | Theme Key
---|---
`fontFamily` | `fonts`
`fontSize` | `fontSizes`
`fontWeight` | `fontWeights`
`lineHeight` | `lineHeights`
`letterSpacing` | `letterSpacings`
`color` | `colors`
`backgroundColor`, `bg` | `colors`
`margin`, `m` | `space`
`marginTop`, `mt` | `space`
`marginRight`, `mr` | `space`
`marginBottom`, `mb` | `space`
`marginLeft`, `ml` | `space`
`marginX`, `mx` | `space`
`marginY`, `my` | `space`
`padding`, `p` | `space`
`paddingTop`, `pt` | `space`
`paddingRight`, `pr` | `space`
`paddingBottom`, `pb` | `space`
`paddingLeft`, `pl` | `space`
`paddingX`, `px` | `space`
`paddingY`, `py` | `space`
`top` | `space`
`bottom` | `space`
`left` | `space`
`right` | `space`
`border` | `borders`
`borderTop` | `borders`
`borderRight` | `borders`
`borderBottom` | `borders`
`borderLeft` | `borders`
`borderColor` | `colors`
`borderWidth` | `borderWidths`
`borderStyle` | `borderStyles`
`borderRadius` | `radii`
`boxShadow` | `shadows`
`textShadow` | `shadows`
`zIndex` | `zIndices`
`width` | `sizes`
`minWidth` | `sizes`
`maxWidth` | `sizes`
`height` | `sizes`
`minHeight` | `sizes`
`maxHeight` | `sizes`
`size` | `sizes`

## Responsive Arrays

All CSS properties accept arrays as values for responsive styles.

```jsx
<div
  css={css({
    fontSize: [ 4, 5, 6 ],
  })}
/>
```

In this example, `fontSize` accepts an array, picking up values from the `theme.fontSizes` scale, and `borderBottom` is passed through as plain CSS.

```jsx
<div
  css={css({
    // Styled System key
    fontSize: [ 3, 4, 5 ],
    // CSS property
    borderBottom: '2px solid tomato',
  })}
/>
```

MIT License
