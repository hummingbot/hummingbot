# @mapbox/hast-util-table-cell-style

[![Build Status](https://travis-ci.org/mapbox/hast-util-table-cell-style.svg?branch=master)](https://travis-ci.org/mapbox/hast-util-table-cell-style)

Transform deprecated styling attributes on [HAST] table cells to inline styles.

## About

[HAST] is the abstract syntax (AST) tree representing HTML that [rehype] uses.

If you use [remark] to process Markdown as [GitHub Flavored Markdown], you may find that your table cell elements end up with `align` attributes.
However, `align` on these elements was deprecated in HTML5: [the suggestion](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/td) is to use a `style` attribute that sets `text-align`, instead.

This matters because more recent syntaxes might altogether ignore `align` or other deprecated styling attributes.
React, for example, [does not support `align` attributes](https://reactjs.org/docs/dom-elements.html#all-supported-html-attributes); so if you try to transform Markdown to React elements, you'll lose your `align` values.
([remark-react] had to [confront this issue](https://github.com/mapbox/remark-react/issues/28).)

This simple utility transforms the following deprecated styling attributes on `<td>`, `<th>`, and `<tr>` elements to equivalent inline styles:

- `align`
- `valign`
- `width`
- `height`

## Installation

```
npm install @mapbox/hast-util-table-cell-style
```

## Usage

```js
const tableCellStyle = require('@mapbox/hast-util-table-cell-style');

// Use rehype to get an AST.
const transformed = tableCellStyle(ast);
```

Mutates the [HAST] AST you pass in, and returns it.

[HAST]: https://github.com/syntax-tree/hast
[rehype]: https://github.com/rehypejs/rehype
[remark]: https://github.com/remarkjs/remark
[GitHub Flavored Markdown]: https://help.github.com/articles/getting-started-with-writing-and-formatting-on-github/
[remark-react]: https://github.com/mapbox/remark-react