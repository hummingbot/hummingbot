# nano-css

[![][npm-badge]][npm-url] [![][travis-badge]][travis-url]

__Tiny [5<sup>th</sup> generation](https://github.com/streamich/freestyler/blob/master/docs/en/generations.md#5th-generation) CSS-in-JS library__ that you can actually use in production.
__Motto of `nano-css` is simple__: *create the smallest possible CSS-in-JS library and provide all features of any other library through addons.*

- __Only [0.5 Kb](https://bundlephobia.com/result?p=nano-css@1.15.3)__ in base configuration, *e.g. [`styled-components`](https://github.com/styled-components/styled-components) is [15.1Kb](https://bundlephobia.com/result?p=styled-components@3.2.5)*
- __Library-agnostic__ &mdash; use it standalone, with React, Preact, Vue.js, or any other library
- __Isomorphic__ &mdash; render on server and browser, generates stable class names, and re-hydrates
- __Performant__ &mdash; [*simply the fastest library*](https://github.com/streamich/CSS-IN-JS-Benchmarks/blob/master/RESULT.md); does not create wrapper components, does not use inline styles or inline `<style>` elements, but caches all styles for re-use and injects CSS using `.insertRule()` for performance
- __`@media` queries__ and __animation `@keyframes`__ are supported
- __Auto-prefixes__ your styles
- __Extract CSS__ into external style sheet
- __Public domain__ &mdash; [Unlicense license](./LICENSE)


## Reference

- [Installation](./docs/Installation.md)
- [Addons](./docs/Addons.md)
  - [`put()`](./docs/put.md) &mdash; [*demo!*](https://codesandbox.io/s/nkovxrzyv4)
  - [`rule()`](./docs/rule.md) &mdash; [*demo!*](https://codesandbox.io/s/oxlj92m1m9)
  - [`drule()`](./docs/drule.md) &mdash; [*demo!*](https://codesandbox.io/s/9jq5zmm91p)
  - [`sheet()`](./docs/sheet.md) &mdash; [*demo!*](https://codesandbox.io/s/wyw093m7kw)
  - [`dsheet()`](./docs/dsheet.md) &mdash; [*demo!*](https://codesandbox.io/s/q7rx4981vq)
  - [`jsx()`](./docs/jsx.md) &mdash; [*demo!*](https://codesandbox.io/s/5y63x88504)
  - [`useStyles()`](./docs/useStyles.md) &mdash; [*demo!*](https://codesandbox.io/s/o5k9jjo306)
  - [`withStyles()`](./docs/withStyles.md) &mdash; [*demo!*](https://codesandbox.io/s/5k3jvkk31l)
  - [`decorator`](./docs/decorator.md) &mdash; [*demo № 1*](https://codesandbox.io/s/j442958125) and [*demo № 2*](https://codesandbox.io/s/3qjzv35941)
  - [`component`](./docs/component.md) &mdash; [*demo!*](https://codesandbox.io/s/yk8pk4v95j)
  - [`style()`](./docs/style.md) &mdash; [*demo!*](https://codesandbox.io/s/53qk3qkopn)
  - [`styled()()`](./docs/styled.md) &mdash; [*demo!*](https://codesandbox.io/s/w667y036p5)
  - [`hyperstyle()`](./docs/hyperstyle.md) &mdash; [*demo!*](https://codesandbox.io/s/wqny7z17x8)
  - [`stable`](./docs/stable.md)
  - [`atoms`](./docs/atoms.md) &mdash; [*demo!*](https://codesandbox.io/s/rlkxl6o9v4)
  - [`emmet`](./docs/emmet.md)
  - [`nesting`](./docs/nesting.md)
  - [`keyframes()`](./docs/keyframes.md)
  - [`hydrate()`](./docs/hydrate.md)
  - [`prefixer`](./docs/prefixer.md)
  - [`stylis`](./docs/stylis.md)
  - [`unitless`](./docs/unitless.md)
  - [`!important`](./docs/important.md)
  - [`:global`](./docs/global.md)
  - [`animate/*`](./docs/animations.md)
  - [`reset/*`](./docs/resets.md)
  - [`reset-font`](./docs/reset-font.md)
  - [`googleFont()`](./docs/googleFont.md)
  - [`limit`](./docs/limit.md)
  - [`amp`](./docs/amp.md)
  - [`virtual`](./docs/virtual.md)
  - [`spread`](./docs/spread.md)
  - [`array`](./docs/array.md)
  - [`snake`](./docs/snake.md) &mdash; [*demo!*](https://codesandbox.io/s/mo7n1857zj)
  - [`tachyons`](./docs/tachyons.md)
  - [`rtl`](./docs/rtl.md)
  - [`extract`](./docs/extract.md)
  - [`sourcemaps`](./docs/sourcemaps.md)
  - [`.units`](./docs/units.md)
  - [`cssom`](./docs/cssom.md)
  - [`vcssom`](./docs/vcssom.md)
- [Presets](./docs/Presets.md)
- [Server-side rendering](./docs/SSR.md)


[npm-url]: https://www.npmjs.com/package/nano-css
[npm-badge]: https://img.shields.io/npm/v/nano-css.svg
[travis-url]: https://travis-ci.org/streamich/nano-css
[travis-badge]: https://travis-ci.org/streamich/nano-css.svg?branch=master
