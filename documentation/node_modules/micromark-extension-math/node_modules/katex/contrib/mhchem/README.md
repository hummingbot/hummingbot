# mhchem extension

This extension adds to KaTeX the `\ce` and `\pu` functions from the [mhchem](https://mhchem.github.io/MathJax-mhchem/) package.

### Usage

This extension isn't part of core KaTeX, so the script should be separately included. Write the following line into the HTML page's `<head>`. Place it *after* the line that calls `katex.js`.

```html
<script src="https://cdn.jsdelivr.net/npm/katex@0.12.0/dist/contrib/mhchem.min.js" integrity="sha384-5gCAXJ0ZgozlShOzzT0OWArn7yCPGWVIvgo+BAd8NUKbCmulrJiQuCVR9cHlPHeG"></script>
```

### Syntax

See the [mhchem Manual](https://mhchem.github.io/MathJax-mhchem/) for a full explanation of the input syntax, with working examples. The manual also includes a demonstration box.

Note that old versions of `mhchem.sty` used `\cf` for chemical formula and `\ce` for chemical equations, but `\cf` has been deprecated in place of `\ce`. This extension supports only `\ce`. You can define a macro mapping `\cf` to `\ce` if needed.

### Browser Support

This extension has been tested on Chrome, Firefox, Opera, and Edge.
