# svg-tag-names

[![Build][build-badge]][build]
[![Downloads][downloads-badge]][downloads]
[![Size][size-badge]][size]

List of known SVG tag names.
Includes the elements from [SVG 1.1][svg11], [SVG Tiny 1.2][svgtiny12], and
[SVG 2][svg2].

The repo contains a script to crawl specs to include newly introduced names.

## Install

[npm][]:

```sh
npm install svg-tag-names
```

## Use

```js
var svgTagNames = require('svg-tag-names')

console.log(svgTagNames.length) // => 94

console.log(svgTagNames.slice(0, 20))
```

Yields:

```js
[
  'a',
  'altGlyph',
  'altGlyphDef',
  'altGlyphItem',
  'animate',
  'animateColor',
  'animateMotion',
  'animateTransform',
  'animation',
  'audio',
  'canvas',
  'circle',
  'clipPath',
  'color-profile',
  'cursor',
  'defs',
  'desc',
  'discard',
  'ellipse',
  'feBlend'
]
```

## API

### `svgTagNames`

`Array.<string>` — List of case-sensitive tag names.

## Related

*   [`html-tag-names`](https://github.com/wooorm/html-tag-names)
    — List of HTML tags
*   [`mathml-tag-names`](https://github.com/wooorm/mathml-tag-names)
    — List of MathML tags
*   [`svg-element-attributes`](https://github.com/wooorm/svg-element-attributes)
    — Map of SVG elements to allowed attributes
*   [`html-element-attributes`](https://github.com/wooorm/html-element-attributes)
    — Map of HTML elements to allowed attributes
*   [`aria-attributes`](https://github.com/wooorm/aria-attributes)
    — List of ARIA attributes

## License

[MIT][license] © [Titus Wormer][author]

<!-- Definition -->

[build-badge]: https://img.shields.io/travis/wooorm/svg-tag-names.svg

[build]: https://travis-ci.org/wooorm/svg-tag-names

[downloads-badge]: https://img.shields.io/npm/dm/svg-tag-names.svg

[downloads]: https://www.npmjs.com/package/svg-tag-names

[size-badge]: https://img.shields.io/bundlephobia/minzip/svg-tag-names.svg

[size]: https://bundlephobia.com/result?p=svg-tag-names

[npm]: https://docs.npmjs.com/cli/install

[license]: license

[author]: https://wooorm.com

[svg11]: https://www.w3.org/TR/SVG11/eltindex.html

[svgtiny12]: https://www.w3.org/TR/SVGTiny12/elementTable.html

[svg2]: https://www.w3.org/TR/SVG2/eltindex.html
