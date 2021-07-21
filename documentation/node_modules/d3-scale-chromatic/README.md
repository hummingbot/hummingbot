# d3-scale-chromatic

This module provides sequential, diverging and categorical color schemes designed to work with [d3-scale](https://github.com/d3/d3-scale)’s [d3.scaleOrdinal](https://github.com/d3/d3-scale#ordinal-scales) and [d3.scaleSequential](https://github.com/d3/d3-scale#sequential-scales). Most of these schemes are derived from Cynthia A. Brewer’s [ColorBrewer](http://colorbrewer2.org). Since ColorBrewer publishes only discrete color schemes, the sequential and diverging scales are interpolated using [uniform B-splines](https://bl.ocks.org/mbostock/048d21cf747371b11884f75ad896e5a5).

For example, to create a categorical color scale using the [Accent](#schemeAccent) color scheme:

```js
var accent = d3.scaleOrdinal(d3.schemeAccent);
```

To create a sequential discrete nine-color scale using the [Blues](#schemeBlues) color scheme:

```js
var blues = d3.scaleOrdinal(d3.schemeBlues[9]);
```

To create a diverging, continuous color scale using the [PiYG](#interpolatePiYG) color scheme:

```js
var piyg = d3.scaleSequential(d3.interpolatePiYG);
```

## Installing

If you use NPM, `npm install d3-scale-chromatic`. Otherwise, download the [latest release](https://github.com/d3/d3-scale-chromatic/releases/latest) or load directly from [d3js.org](https://d3js.org) as a [standalone library](https://d3js.org/d3-scale-chromatic.v1.min.js). AMD, CommonJS, and vanilla environments are supported. In vanilla, a `d3` global is exported:

```html
<script src="https://d3js.org/d3-color.v1.min.js"></script>
<script src="https://d3js.org/d3-interpolate.v1.min.js"></script>
<script src="https://d3js.org/d3-scale-chromatic.v1.min.js"></script>
<script>

var yellow = d3.interpolateYlGn(0), // "rgb(255, 255, 229)"
    yellowGreen = d3.interpolateYlGn(0.5), // "rgb(120, 197, 120)"
    green = d3.interpolateYlGn(1); // "rgb(0, 69, 41)"

</script>
```

Or, as part of the [D3 default bundle](https://github.com/d3/d3):

```html
<script src="https://d3js.org/d3.v5.min.js"></script>
<script>

var yellow = d3.interpolateYlGn(0), // "rgb(255, 255, 229)"
    yellowGreen = d3.interpolateYlGn(0.5), // "rgb(120, 197, 120)"
    green = d3.interpolateYlGn(1); // "rgb(0, 69, 41)"

</script>
```

[Try d3-scale-chromatic in your browser.](https://observablehq.com/collection/@d3/d3-scale-chromatic)

## API Reference

### Categorical

<a name="schemeCategory10" href="#schemeCategory10">#</a> d3.<b>schemeCategory10</b> [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/categorical/category10.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/category10.png" width="100%" height="40" alt="category10">

An array of ten categorical colors represented as RGB hexadecimal strings.

<a href="#schemeAccent" name="schemeAccent">#</a> d3.<b>schemeAccent</b> [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/categorical/Accent.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/Accent.png" width="100%" height="40" alt="Accent">

An array of eight categorical colors represented as RGB hexadecimal strings.

<a href="#schemeDark2" name="schemeDark2">#</a> d3.<b>schemeDark2</b> [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/categorical/Dark2.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/Dark2.png" width="100%" height="40" alt="Dark2">

An array of eight categorical colors represented as RGB hexadecimal strings.

<a href="#schemePaired" name="schemePaired">#</a> d3.<b>schemePaired</b> [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/categorical/Paired.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/Paired.png" width="100%" height="40" alt="Paired">

An array of twelve categorical colors represented as RGB hexadecimal strings.

<a href="#schemePastel1" name="schemePastel1">#</a> d3.<b>schemePastel1</b> [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/categorical/Pastel1.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/Pastel1.png" width="100%" height="40" alt="Pastel1">

An array of nine categorical colors represented as RGB hexadecimal strings.

<a href="#schemePastel2" name="schemePastel2">#</a> d3.<b>schemePastel2</b> [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/categorical/Pastel2.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/Pastel2.png" width="100%" height="40" alt="Pastel2">

An array of eight categorical colors represented as RGB hexadecimal strings.

<a href="#schemeSet1" name="schemeSet1">#</a> d3.<b>schemeSet1</b> [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/categorical/Set1.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/Set1.png" width="100%" height="40" alt="Set1">

An array of nine categorical colors represented as RGB hexadecimal strings.

<a href="#schemeSet2" name="schemeSet2">#</a> d3.<b>schemeSet2</b> [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/categorical/Set2.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/Set2.png" width="100%" height="40" alt="Set2">

An array of eight categorical colors represented as RGB hexadecimal strings.

<a href="#schemeSet3" name="schemeSet3">#</a> d3.<b>schemeSet3</b> [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/categorical/Set3.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/Set3.png" width="100%" height="40" alt="Set3">

An array of twelve categorical colors represented as RGB hexadecimal strings.

<a href="#schemeTableau10" name="schemeTableau10">#</a> d3.<b>schemeTableau10</b> [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/categorical/Tableau10.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/Tableau10.png" width="100%" height="40" alt="Tableau10">

An array of ten categorical colors authored by Tableau as part of [Tableau 10](https://www.tableau.com/about/blog/2016/7/colors-upgrade-tableau-10-56782) represented as RGB hexadecimal strings.

### Diverging

Diverging color schemes are available as continuous interpolators (often used with [d3.scaleSequential](https://github.com/d3/d3-scale/blob/master/README.md#sequential-scales)) and as discrete schemes (often used with [d3.scaleOrdinal](https://github.com/d3/d3-scale/blob/master/README.md#ordinal-scales)). Each discrete scheme, such as [d3.schemeBrBG](#schemeBrBG), is represented as an array of arrays of hexadecimal color strings. The *k*th element of this array contains the color scheme of size *k*; for example, `d3.schemeBrBG[9]` contains an array of nine strings representing the nine colors of the brown-blue-green diverging color scheme. Diverging color schemes support a size *k* ranging from 3 to 11.

<a href="#interpolateBrBG" name="interpolateBrBG">#</a> d3.<b>interpolateBrBG</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/diverging/BrBG.js "Source")
<br><a href="#schemeBrBG" name="schemeBrBG">#</a> d3.<b>schemeBrBG</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/BrBG.png" width="100%" height="40" alt="BrBG">

Given a number *t* in the range [0,1], returns the corresponding color from the “BrBG” diverging color scheme represented as an RGB string.

<a href="#interpolatePRGn" name="interpolatePRGn">#</a> d3.<b>interpolatePRGn</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/diverging/PRGn.js "Source")
<br><a href="#schemePRGn" name="schemePRGn">#</a> d3.<b>schemePRGn</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/PRGn.png" width="100%" height="40" alt="PRGn">

Given a number *t* in the range [0,1], returns the corresponding color from the “PRGn” diverging color scheme represented as an RGB string.

<a href="#interpolatePiYG" name="interpolatePiYG">#</a> d3.<b>interpolatePiYG</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/diverging/PiYG.js "Source")
<br><a href="#schemePiYG" name="schemePiYG">#</a> d3.<b>schemePiYG</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/PiYG.png" width="100%" height="40" alt="PiYG">

Given a number *t* in the range [0,1], returns the corresponding color from the “PiYG” diverging color scheme represented as an RGB string.

<a href="#interpolatePuOr" name="interpolatePuOr">#</a> d3.<b>interpolatePuOr</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/diverging/PuOr.js "Source")
<br><a href="#schemePuOr" name="schemePuOr">#</a> d3.<b>schemePuOr</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/PuOr.png" width="100%" height="40" alt="PuOr">

Given a number *t* in the range [0,1], returns the corresponding color from the “PuOr” diverging color scheme represented as an RGB string.

<a href="#interpolateRdBu" name="interpolateRdBu">#</a> d3.<b>interpolateRdBu</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/diverging/RdBu.js "Source")
<br><a href="#schemeRdBu" name="schemeRdBu">#</a> d3.<b>schemeRdBu</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/RdBu.png" width="100%" height="40" alt="RdBu">

Given a number *t* in the range [0,1], returns the corresponding color from the “RdBu” diverging color scheme represented as an RGB string.

<a href="#interpolateRdGy" name="interpolateRdGy">#</a> d3.<b>interpolateRdGy</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/diverging/RdGy.js "Source")
<br><a href="#schemeRdGy" name="schemeRdGy">#</a> d3.<b>schemeRdGy</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/RdGy.png" width="100%" height="40" alt="RdGy">

Given a number *t* in the range [0,1], returns the corresponding color from the “RdGy” diverging color scheme represented as an RGB string.

<a href="#interpolateRdYlBu" name="interpolateRdYlBu">#</a> d3.<b>interpolateRdYlBu</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/diverging/RdYlBu.js "Source")
<br><a href="#schemeRdYlBu" name="schemeRdYlBu">#</a> d3.<b>schemeRdYlBu</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/RdYlBu.png" width="100%" height="40" alt="RdYlBu">

Given a number *t* in the range [0,1], returns the corresponding color from the “RdYlBu” diverging color scheme represented as an RGB string.

<a href="#interpolateRdYlGn" name="interpolateRdYlGn">#</a> d3.<b>interpolateRdYlGn</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/diverging/RdYlGn.js "Source")
<br><a href="#schemeRdYlGn" name="schemeRdYlGn">#</a> d3.<b>schemeRdYlGn</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/RdYlGn.png" width="100%" height="40" alt="RdYlGn">

Given a number *t* in the range [0,1], returns the corresponding color from the “RdYlGn” diverging color scheme represented as an RGB string.

<a href="#interpolateSpectral" name="interpolateSpectral">#</a> d3.<b>interpolateSpectral</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/diverging/Spectral.js "Source")
<br><a href="#schemeSpectral" name="schemeSpectral">#</a> d3.<b>schemeSpectral</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/Spectral.png" width="100%" height="40" alt="Spectral">

Given a number *t* in the range [0,1], returns the corresponding color from the “Spectral” diverging color scheme represented as an RGB string.

### Sequential (Single Hue)

Sequential, single-hue color schemes are available as continuous interpolators (often used with [d3.scaleSequential](https://github.com/d3/d3-scale/blob/master/README.md#sequential-scales)) and as discrete schemes (often used with [d3.scaleOrdinal](https://github.com/d3/d3-scale/blob/master/README.md#ordinal-scales)). Each discrete scheme, such as [d3.schemeBlues](#schemeBlues), is represented as an array of arrays of hexadecimal color strings. The *k*th element of this array contains the color scheme of size *k*; for example, `d3.schemeBlues[9]` contains an array of nine strings representing the nine colors of the blue sequential color scheme. Sequential, single-hue color schemes support a size *k* ranging from 3 to 9.

<a href="#interpolateBlues" name="interpolateBlues">#</a> d3.<b>interpolateBlues</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-single/Blues.js "Source")
<br><a href="#schemeBlues" name="schemeBlues">#</a> d3.<b>schemeBlues</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/Blues.png" width="100%" height="40" alt="Blues">

Given a number *t* in the range [0,1], returns the corresponding color from the “Blues” sequential color scheme represented as an RGB string.

<a href="#interpolateGreens" name="interpolateGreens">#</a> d3.<b>interpolateGreens</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-single/Greens.js "Source")
<br><a href="#schemeGreens" name="schemeGreens">#</a> d3.<b>schemeGreens</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/Greens.png" width="100%" height="40" alt="Greens">

Given a number *t* in the range [0,1], returns the corresponding color from the “Greens” sequential color scheme represented as an RGB string.

<a href="#interpolateGreys" name="interpolateGreys">#</a> d3.<b>interpolateGreys</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-single/Greys.js "Source")
<br><a href="#schemeGreys" name="schemeGreys">#</a> d3.<b>schemeGreys</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/Greys.png" width="100%" height="40" alt="Greys">

Given a number *t* in the range [0,1], returns the corresponding color from the “Greys” sequential color scheme represented as an RGB string.

<a href="#interpolateOranges" name="interpolateOranges">#</a> d3.<b>interpolateOranges</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-single/Oranges.js "Source")
<br><a href="#schemeOranges" name="schemeOranges">#</a> d3.<b>schemeOranges</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/Oranges.png" width="100%" height="40" alt="Oranges">

Given a number *t* in the range [0,1], returns the corresponding color from the “Oranges” sequential color scheme represented as an RGB string.

<a href="#interpolatePurples" name="interpolatePurples">#</a> d3.<b>interpolatePurples</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-single/Purples.js "Source")
<br><a href="#schemePurples" name="schemePurples">#</a> d3.<b>schemePurples</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/Purples.png" width="100%" height="40" alt="Purples">

Given a number *t* in the range [0,1], returns the corresponding color from the “Purples” sequential color scheme represented as an RGB string.

<a href="#interpolateReds" name="interpolateReds">#</a> d3.<b>interpolateReds</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-single/Reds.js "Source")
<br><a href="#schemeReds" name="schemeReds">#</a> d3.<b>schemeReds</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/Reds.png" width="100%" height="40" alt="Reds">

Given a number *t* in the range [0,1], returns the corresponding color from the “Reds” sequential color scheme represented as an RGB string.

### Sequential (Multi-Hue)

Sequential, multi-hue color schemes are available as continuous interpolators (often used with [d3.scaleSequential](https://github.com/d3/d3-scale/blob/master/README.md#sequential-scales)) and as discrete schemes (often used with [d3.scaleOrdinal](https://github.com/d3/d3-scale/blob/master/README.md#ordinal-scales)). Each discrete scheme, such as [d3.schemeBuGn](#schemeBuGn), is represented as an array of arrays of hexadecimal color strings. The *k*th element of this array contains the color scheme of size *k*; for example, `d3.schemeBuGn[9]` contains an array of nine strings representing the nine colors of the blue-green sequential color scheme. Sequential, multi-hue color schemes support a size *k* ranging from 3 to 9.

<a name="interpolateTurbo" href="#interpolateTurbo">#</a> d3.<b>interpolateTurbo</b>(<i>t</i>) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/turbo.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/turbo.png" width="100%" height="40" alt="turbo">

Given a number *t* in the range [0,1], returns the corresponding color from the “turbo” color scheme by [Google AI](https://ai.googleblog.com/2019/08/turbo-improved-rainbow-colormap-for.html).

<a name="interpolateViridis" href="#interpolateViridis">#</a> d3.<b>interpolateViridis</b>(<i>t</i>) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/viridis.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/viridis.png" width="100%" height="40" alt="viridis">

Given a number *t* in the range [0,1], returns the corresponding color from the “viridis” perceptually-uniform color scheme designed by [van der Walt, Smith and Firing](https://bids.github.io/colormap/) for matplotlib, represented as an RGB string.

<a name="interpolateInferno" href="#interpolateInferno">#</a> d3.<b>interpolateInferno</b>(<i>t</i>) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/viridis.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/inferno.png" width="100%" height="40" alt="inferno">

Given a number *t* in the range [0,1], returns the corresponding color from the “inferno” perceptually-uniform color scheme designed by [van der Walt and Smith](https://bids.github.io/colormap/) for matplotlib, represented as an RGB string.

<a name="interpolateMagma" href="#interpolateMagma">#</a> d3.<b>interpolateMagma</b>(<i>t</i>) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/viridis.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/magma.png" width="100%" height="40" alt="magma">

Given a number *t* in the range [0,1], returns the corresponding color from the “magma” perceptually-uniform color scheme designed by [van der Walt and Smith](https://bids.github.io/colormap/) for matplotlib, represented as an RGB string.

<a name="interpolatePlasma" href="#interpolatePlasma">#</a> d3.<b>interpolatePlasma</b>(<i>t</i>) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/viridis.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/plasma.png" width="100%" height="40" alt="plasma">

Given a number *t* in the range [0,1], returns the corresponding color from the “plasma” perceptually-uniform color scheme designed by [van der Walt and Smith](https://bids.github.io/colormap/) for matplotlib, represented as an RGB string.

<a name="interpolateCividis" href="#interpolateCividis">#</a> d3.<b>interpolateCividis</b>(<i>t</i>) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/cividis.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/cividis.png" width="100%" height="40" alt="cividis">

Given a number *t* in the range [0,1], returns the corresponding color from the “cividis” color vision deficiency-optimized color scheme designed by [Nuñez, Anderton, and Renslow](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0199239), represented as an RGB string.

<a name="interpolateWarm" href="#interpolateWarm">#</a> d3.<b>interpolateWarm</b>(<i>t</i>) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/rainbow.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/warm.png" width="100%" height="40" alt="warm">

Given a number *t* in the range [0,1], returns the corresponding color from a 180° rotation of [Niccoli’s perceptual rainbow](https://mycarta.wordpress.com/2013/02/21/perceptual-rainbow-palette-the-method/), represented as an RGB string.

<a name="interpolateCool" href="#interpolateCool">#</a> d3.<b>interpolateCool</b>(<i>t</i>) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/rainbow.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/cool.png" width="100%" height="40" alt="cool">

Given a number *t* in the range [0,1], returns the corresponding color from [Niccoli’s perceptual rainbow](https://mycarta.wordpress.com/2013/02/21/perceptual-rainbow-palette-the-method/), represented as an RGB string.

<a name="interpolateCubehelixDefault" href="#interpolateCubehelixDefault">#</a> d3.<b>interpolateCubehelixDefault</b>(<i>t</i>) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/cubehelix.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/cubehelix.png" width="100%" height="40" alt="cubehelix">

Given a number *t* in the range [0,1], returns the corresponding color from [Green’s default Cubehelix](https://www.mrao.cam.ac.uk/~dag/CUBEHELIX/) represented as an RGB string.

<a href="#interpolateBuGn" name="interpolateBuGn">#</a> d3.<b>interpolateBuGn</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/BuGn.js "Source")
<br><a href="#schemeBuGn" name="schemeBuGn">#</a> d3.<b>schemeBuGn</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/BuGn.png" width="100%" height="40" alt="BuGn">

Given a number *t* in the range [0,1], returns the corresponding color from the “BuGn” sequential color scheme represented as an RGB string.

<a href="#interpolateBuPu" name="interpolateBuPu">#</a> d3.<b>interpolateBuPu</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/BuPu.js "Source")
<br><a href="#schemeBuPu" name="schemeBuPu">#</a> d3.<b>schemeBuPu</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/BuPu.png" width="100%" height="40" alt="BuPu">

Given a number *t* in the range [0,1], returns the corresponding color from the “BuPu” sequential color scheme represented as an RGB string.

<a href="#interpolateGnBu" name="interpolateGnBu">#</a> d3.<b>interpolateGnBu</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/GnBu.js "Source")
<br><a href="#schemeGnBu" name="schemeGnBu">#</a> d3.<b>schemeGnBu</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/GnBu.png" width="100%" height="40" alt="GnBu">

Given a number *t* in the range [0,1], returns the corresponding color from the “GnBu” sequential color scheme represented as an RGB string.

<a href="#interpolateOrRd" name="interpolateOrRd">#</a> d3.<b>interpolateOrRd</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/OrRd.js "Source")
<br><a href="#schemeOrRd" name="schemeOrRd">#</a> d3.<b>schemeOrRd</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/OrRd.png" width="100%" height="40" alt="OrRd">

Given a number *t* in the range [0,1], returns the corresponding color from the “OrRd” sequential color scheme represented as an RGB string.

<a href="#interpolatePuBuGn" name="interpolatePuBuGn">#</a> d3.<b>interpolatePuBuGn</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/PuBuGn.js "Source")
<br><a href="#schemePuBuGn" name="schemePuBuGn">#</a> d3.<b>schemePuBuGn</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/PuBuGn.png" width="100%" height="40" alt="PuBuGn">

Given a number *t* in the range [0,1], returns the corresponding color from the “PuBuGn” sequential color scheme represented as an RGB string.

<a href="#interpolatePuBu" name="interpolatePuBu">#</a> d3.<b>interpolatePuBu</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/PuBu.js "Source")
<br><a href="#schemePuBu" name="schemePuBu">#</a> d3.<b>schemePuBu</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/PuBu.png" width="100%" height="40" alt="PuBu">

Given a number *t* in the range [0,1], returns the corresponding color from the “PuBu” sequential color scheme represented as an RGB string.

<a href="#interpolatePuRd" name="interpolatePuRd">#</a> d3.<b>interpolatePuRd</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/PuRd.js "Source")
<br><a href="#schemePuRd" name="schemePuRd">#</a> d3.<b>schemePuRd</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/PuRd.png" width="100%" height="40" alt="PuRd">

Given a number *t* in the range [0,1], returns the corresponding color from the “PuRd” sequential color scheme represented as an RGB string.

<a href="#interpolateRdPu" name="interpolateRdPu">#</a> d3.<b>interpolateRdPu</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/RdPu.js "Source")
<br><a href="#schemeRdPu" name="schemeRdPu">#</a> d3.<b>schemeRdPu</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/RdPu.png" width="100%" height="40" alt="RdPu">

Given a number *t* in the range [0,1], returns the corresponding color from the “RdPu” sequential color scheme represented as an RGB string.

<a href="#interpolateYlGnBu" name="interpolateYlGnBu">#</a> d3.<b>interpolateYlGnBu</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/YlGnBu.js "Source")
<br><a href="#schemeYlGnBu" name="schemeYlGnBu">#</a> d3.<b>schemeYlGnBu</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/YlGnBu.png" width="100%" height="40" alt="YlGnBu">

Given a number *t* in the range [0,1], returns the corresponding color from the “YlGnBu” sequential color scheme represented as an RGB string.

<a href="#interpolateYlGn" name="interpolateYlGn">#</a> d3.<b>interpolateYlGn</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/YlGn.js "Source")
<br><a href="#schemeYlGn" name="schemeYlGn">#</a> d3.<b>schemeYlGn</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/YlGn.png" width="100%" height="40" alt="YlGn">

Given a number *t* in the range [0,1], returns the corresponding color from the “YlGn” sequential color scheme represented as an RGB string.

<a href="#interpolateYlOrBr" name="interpolateYlOrBr">#</a> d3.<b>interpolateYlOrBr</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/YlOrBr.js "Source")
<br><a href="#schemeYlOrBr" name="schemeYlOrBr">#</a> d3.<b>schemeYlOrBr</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/YlOrBr.png" width="100%" height="40" alt="YlOrBr">

Given a number *t* in the range [0,1], returns the corresponding color from the “YlOrBr” sequential color scheme represented as an RGB string.

<a href="#interpolateYlOrRd" name="interpolateYlOrRd">#</a> d3.<b>interpolateYlOrRd</b>(*t*) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/YlOrRd.js "Source")
<br><a href="#schemeYlOrRd" name="schemeYlOrRd">#</a> d3.<b>schemeYlOrRd</b>[*k*]

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/YlOrRd.png" width="100%" height="40" alt="YlOrRd">

Given a number *t* in the range [0,1], returns the corresponding color from the “YlOrRd” sequential color scheme represented as an RGB string.

### Cyclical

<a name="interpolateRainbow" href="#interpolateRainbow">#</a> d3.<b>interpolateRainbow</b>(<i>t</i>) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/rainbow.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/rainbow.png" width="100%" height="40" alt="rainbow">

Given a number *t* in the range [0,1], returns the corresponding color from [d3.interpolateWarm](#interpolateWarm) scale from [0.0, 0.5] followed by the [d3.interpolateCool](#interpolateCool) scale from [0.5, 1.0], thus implementing the cyclical [less-angry rainbow](http://bl.ocks.org/mbostock/310c99e53880faec2434) color scheme.

<a name="interpolateSinebow" href="#interpolateSinebow">#</a> d3.<b>interpolateSinebow</b>(<i>t</i>) [<>](https://github.com/d3/d3-scale-chromatic/blob/master/src/sequential-multi/sinebow.js "Source")

<img src="https://raw.githubusercontent.com/d3/d3-scale-chromatic/master/img/sinebow.png" width="100%" height="40" alt="sinebow">

Given a number *t* in the range [0,1], returns the corresponding color from the “sinebow” color scheme by [Jim Bumgardner](https://krazydad.com/tutorials/makecolors.php) and [Charlie Loyd](http://basecase.org/env/on-rainbows).
