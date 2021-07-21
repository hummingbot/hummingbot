# d3-contour

This library computes contour polygons by applying [marching squares](https://en.wikipedia.org/wiki/Marching_squares) to a rectangular array of numeric values. For example, here is Maungawhau’s topology (the classic `volcano` dataset and `terrain.colors` from R):

[<img alt="Contour Plot" src="https://raw.githubusercontent.com/d3/d3-contour/master/img/volcano.gif" width="420" height="295">](https://bl.ocks.org/mbostock/4241134)

For each [threshold value](#contours_thresholds), the [contour generator](#_contours) constructs a GeoJSON MultiPolygon geometry object representing the area where the input values are greater than or equal to the threshold value. The geometry is in planar coordinates, where ⟨<i>i</i> + 0.5, <i>j</i> + 0.5⟩ corresponds to element <i>i</i> + <i>jn</i> in the input values array. Here is an example that loads a GeoTIFF of surface temperatures, and another that blurs a noisy monochrome PNG to produce smooth contours of cloud fraction:

[<img alt="GeoTiff Contours" src="https://raw.githubusercontent.com/d3/d3-contour/master/img/temperature.png" width="420" height="219">](https://bl.ocks.org/mbostock/4886c227038510f1c103ce305bef6fcc)
[<img alt="Cloud Contours" src="https://raw.githubusercontent.com/d3/d3-contour/master/img/clouds.png" width="420" height="219">](https://bl.ocks.org/mbostock/818053c76d79d4841790c332656bf9da)

Since the contour polygons are GeoJSON, you can transform and display them using standard tools; see [d3.geoPath](https://github.com/d3/d3-geo/blob/master/README.md#geoPath), [d3.geoProject](https://github.com/d3/d3-geo-projection/blob/master/README.md#geoProject) and [d3.geoStitch](https://github.com/d3/d3-geo-projection/blob/master/README.md#geoStitch), for example. Here the above contours of surface temperature are displayed in the Natural Earth projection:

[<img alt="GeoTiff Contours II" src="https://raw.githubusercontent.com/d3/d3-contour/master/img/reprojection.png" width="420" height="219">](https://bl.ocks.org/mbostock/83c0be21dba7602ee14982b020b12f51)

Contour plots can also visualize continuous functions by sampling. Here is the Goldstein–Price function (a test function for global optimization) and a trippy animation of *sin*(*x* + *y*)*sin*(*x* - *y*):

[<img alt="Contour Plot II" src="https://raw.githubusercontent.com/d3/d3-contour/master/img/goldstein-price.png" width="420" height="219">](https://bl.ocks.org/mbostock/f48ff9c1af4d637c9a518727f5fdfef5)
[<img alt="Contour Plot III" src="https://raw.githubusercontent.com/d3/d3-contour/master/img/sin-cos.png" width="420" height="219">](https://bl.ocks.org/mbostock/bf2f5f02b62b5b3bb92ae1b59b53da36)

Contours can also show the [estimated density](#density-estimation) of point clouds, which is especially useful to avoid overplotting in large datasets. This library implements fast two-dimensional kernel density estimation; see [d3.contourDensity](#contourDensity). Here is a scatterplot showing the relationship between the idle duration and eruption duration for Old Faithful:

[<img alt="Density Contours" src="https://raw.githubusercontent.com/d3/d3-contour/master/img/faithful.png" width="420" height="219">](https://bl.ocks.org/mbostock/e3f4376d54e02d5d43ae32a7cf0e6aa9)

And here is a density contour plot showing the relationship between the weight and price of 53,940 diamonds:

[<img alt="Density Contours" src="https://raw.githubusercontent.com/d3/d3-contour/master/img/diamonds.png" width="420" height="420">](https://bl.ocks.org/mbostock/7f5f22524bd1d824dd53c535eda0187f)

## Installing

If you use NPM, `npm install d3-contour`. Otherwise, download the [latest release](https://github.com/d3/d3-contour/releases/latest). You can also load directly from [d3js.org](https://d3js.org), either as a [standalone library](https://d3js.org/d3-contour.v1.min.js) or as part of [D3 4.0](https://github.com/d3/d3). AMD, CommonJS, and vanilla environments are supported. In vanilla, a `d3` global is exported:

```html
<script src="https://d3js.org/d3-contour.v1.min.js"></script>
<script>

// Populate a grid of n×m values where -2 ≤ x ≤ 2 and -2 ≤ y ≤ 1.
var n = 256, m = 256, values = new Array(n * m);
for (var j = 0.5, k = 0; j < m; ++j) {
  for (var i = 0.5; i < n; ++i, ++k) {
    values[k] = goldsteinPrice(i / n * 4 - 2, 1 - j / m * 3);
  }
}

// Compute the contour polygons at log-spaced intervals; returns an array of MultiPolygon.
var contours = d3.contours()
    .size([n, m])
    .thresholds(d3.range(2, 21).map(p => Math.pow(2, p)))
    (values);

// See https://en.wikipedia.org/wiki/Test_functions_for_optimization
function goldsteinPrice(x, y) {
  return (1 + Math.pow(x + y + 1, 2) * (19 - 14 * x + 3 * x * x - 14 * y + 6 * x * x + 3 * y * y))
      * (30 + Math.pow(2 * x - 3 * y, 2) * (18 - 32 * x + 12 * x * x + 48 * y - 36 * x * y + 27 * y * y));
}

</script>
```

[Try d3-contour in your browser.](https://tonicdev.com/npm/d3-contour)

## API Reference

<a name="contours" href="#contours">#</a> d3.<b>contours</b>() [<>](https://github.com/d3/d3-contour/blob/master/src/contours.js "Source")

Constructs a new contour generator with the default settings.

<a name="_contours" href="#_contours">#</a> <i>contours</i>(<i>values</i>) [<>](https://github.com/d3/d3-contour/blob/master/src/contours.js "Source")

Computes the contours for the given array of *values*, returning an array of [GeoJSON](http://geojson.org/geojson-spec.html) [MultiPolygon](http://geojson.org/geojson-spec.html#multipolygon) [geometry objects](http://geojson.org/geojson-spec.html#geometry-objects). Each geometry object represents the area where the input <i>values</i> are greater than or equal to the corresponding [threshold value](#contours_thresholds); the threshold value for each geometry object is exposed as <i>geometry</i>.value.

The input *values* must be an array of length <i>n</i>×<i>m</i> where [<i>n</i>, <i>m</i>] is the contour generator’s [size](#contours_size); furthermore, each <i>values</i>[<i>i</i> + <i>jn</i>] must represent the value at the position ⟨<i>i</i>, <i>j</i>⟩. For example, to construct a 256×256 grid for the [Goldstein–Price function](https://en.wikipedia.org/wiki/Test_functions_for_optimization) where -2 ≤ <i>x</i> ≤ 2 and -2 ≤ <i>y</i> ≤ 1:

```js
var n = 256, m = 256, values = new Array(n * m);
for (var j = 0.5, k = 0; j < m; ++j) {
  for (var i = 0.5; i < n; ++i, ++k) {
    values[k] = goldsteinPrice(i / n * 4 - 2, 1 - j / m * 3);
  }
}

function goldsteinPrice(x, y) {
  return (1 + Math.pow(x + y + 1, 2) * (19 - 14 * x + 3 * x * x - 14 * y + 6 * x * x + 3 * y * y))
      * (30 + Math.pow(2 * x - 3 * y, 2) * (18 - 32 * x + 12 * x * x + 48 * y - 36 * x * y + 27 * y * y));
}
```

The returned geometry objects are typically passed to [d3.geoPath](https://github.com/d3/d3-geo/blob/master/README.md#geoPath) to display, using null or [d3.geoIdentity](https://github.com/d3/d3-geo/blob/master/README.md#geoIdentity) as the associated projection.

<a name="contours_contour" href="#contours_contour">#</a> <i>contours</i>.<b>contour</b>(<i>values</i>, <i>threshold</i>) [<>](https://github.com/d3/d3-contour/blob/master/src/contours.js "Source")

Computes a single contour, returning a [GeoJSON](http://geojson.org/geojson-spec.html) [MultiPolygon](http://geojson.org/geojson-spec.html#multipolygon) [geometry object](http://geojson.org/geojson-spec.html#geometry-objects) representing the area where the input <i>values</i> are greater than or equal to the given [*threshold* value](#contours_thresholds); the threshold value for each geometry object is exposed as <i>geometry</i>.value.

The input *values* must be an array of length <i>n</i>×<i>m</i> where [<i>n</i>, <i>m</i>] is the contour generator’s [size](#contours_size); furthermore, each <i>values</i>[<i>i</i> + <i>jn</i>] must represent the value at the position ⟨<i>i</i>, <i>j</i>⟩. See [*contours*](#_contours) for an example.

<a name="contours_size" href="#contours_size">#</a> <i>contours</i>.<b>size</b>([<i>size</i>]) [<>](https://github.com/d3/d3-contour/blob/master/src/contours.js "Source")

If *size* is specified, sets the expected size of the input *values* grid to the [contour generator](#_contour) and returns the contour generator. The *size* is specified as an array \[<i>n</i>, <i>m</i>\] where <i>n</i> is the number of columns in the grid and <i>m</i> is the number of rows; *n* and *m* must be positive integers. If *size* is not specified, returns the current size which defaults to [1, 1].

<a name="contours_smooth" href="#contours_smooth">#</a> <i>contours</i>.<b>smooth</b>([<i>smooth</i>]) [<>](https://github.com/d3/d3-contour/blob/master/src/contours.js "Source")

If *smooth* is specified, sets whether or not the generated contour polygons are smoothed using linear interpolation. If *smooth* is not specified, returns the current smoothing flag, which defaults to true.

<a name="contours_thresholds" href="#contours_thresholds">#</a> <i>contours</i>.<b>thresholds</b>([<i>thresholds</i>]) [<>](https://github.com/d3/d3-contour/blob/master/src/contours.js "Source")

If *thresholds* is specified, sets the threshold generator to the specified function or array and returns this contour generator. If *thresholds* is not specified, returns the current threshold generator, which by default implements [Sturges’ formula](https://github.com/d3/d3-array/blob/master/README.md#thresholdSturges).

Thresholds are defined as an array of values [*x0*, *x1*, …]. The first [generated contour](#_contour) corresponds to the area where the input values are greater than or equal to *x0*; the second contour corresponds to the area where the input values are greater than or equal to *x1*, and so on. Thus, there is exactly one generated MultiPolygon geometry object for each specified threshold value; the threshold value is exposed as <i>geometry</i>.value.

If a *count* is specified instead of an array of *thresholds*, then the input values’ [extent](https://github.com/d3/d3-array/blob/master/README.md#extent) will be uniformly divided into approximately *count* bins; see [d3.ticks](https://github.com/d3/d3-array/blob/master/README.md#ticks).

## Density Estimation

<a name="contourDensity" href="#contourDensity">#</a> d3.<b>contourDensity</b>() [<>](https://github.com/d3/d3-contour/blob/master/src/density.js "Source")

Constructs a new density estimator with the default settings.

<a name="_density" href="#_density">#</a> <i>density</i>(<i>data</i>) [<>](https://github.com/d3/d3-contour/blob/master/src/density.js "Source")

Estimates the density contours for the given array of *data*, returning an array of [GeoJSON](http://geojson.org/geojson-spec.html) [MultiPolygon](http://geojson.org/geojson-spec.html#multipolygon) [geometry objects](http://geojson.org/geojson-spec.html#geometry-objects). Each geometry object represents the area where the estimated number of points per square pixel is greater than or equal to the corresponding [threshold value](#density_thresholds); the threshold value for each geometry object is exposed as <i>geometry</i>.value. The returned geometry objects are typically passed to [d3.geoPath](https://github.com/d3/d3-geo/blob/master/README.md#geoPath) to display, using null or [d3.geoIdentity](https://github.com/d3/d3-geo/blob/master/README.md#geoIdentity) as the associated projection. See also [d3.contours](#contours).

The *x*- and *y*-coordinate for each data point are computed using [*density*.x](#density_x) and [*density*.y](#density_y). In addition, [*density*.weight](#density_weight) indicates the relative contribution of each data point (default 1). The generated contours are only accurate within the estimator’s [defined size](#density_size).

<a name="density_x" href="#density_x">#</a> <i>density</i>.<b>x</b>([<i>x</i>]) [<>](https://github.com/d3/d3-contour/blob/master/src/density.js "Source")

If *x* is specified, sets the *x*-coordinate accessor. If *x* is not specified, returns the current *x*-coordinate accessor, which defaults to:

```js
function x(d) {
  return d[0];
}
```

<a name="density_y" href="#density_y">#</a> <i>density</i>.<b>y</b>([<i>y</i>]) [<>](https://github.com/d3/d3-contour/blob/master/src/density.js "Source")

If *y* is specified, sets the *y*-coordinate accessor. If *y* is not specified, returns the current *y*-coordinate accessor, which defaults to:

```js
function y(d) {
  return d[1];
}
```

<a name="density_weight" href="#density_weight">#</a> <i>density</i>.<b>weight</b>([<i>weight</i>]) [<>](https://github.com/d3/d3-contour/blob/master/src/density.js "Source")

If *weight* is specified, sets the accessor for point weights. If *weight* is not specified, returns the current point weight accessor, which defaults to:

```js
function weight() {
  return 1;
}
```

<a name="density_size" href="#density_size">#</a> <i>density</i>.<b>size</b>([<i>size</i>]) [<>](https://github.com/d3/d3-contour/blob/master/src/density.js "Source")

If *size* is specified, sets the size of the density estimator to the specified bounds and returns the estimator. The *size* is specified as an array \[<i>width</i>, <i>height</i>\], where <i>width</i> is the maximum *x*-value and <i>height</i> is the maximum *y*-value. If *size* is not specified, returns the current size which defaults to [960, 500]. The [estimated density contours](#_density) are only accurate within the defined size.

<a name="density_cellSize" href="#density_cellSize">#</a> <i>density</i>.<b>cellSize</b>([<i>cellSize</i>]) [<>](https://github.com/d3/d3-contour/blob/master/src/density.js "Source")

If *cellSize* is specified, sets the size of individual cells in the underlying bin grid to the specified positive integer and returns the estimator. If *cellSize* is not specified, returns the current cell size, which defaults to 4. The cell size is rounded down to the nearest power of two. Smaller cells produce more detailed contour polygons, but are more expensive to compute.

<a name="density_thresholds" href="#density_thresholds">#</a> <i>density</i>.<b>thresholds</b>([<i>thresholds</i>]) [<>](https://github.com/d3/d3-contour/blob/master/src/density.js "Source")

If *thresholds* is specified, sets the threshold generator to the specified function or array and returns this contour generator. If *thresholds* is not specified, returns the current threshold generator, which by default generates about twenty nicely-rounded density thresholds.

Thresholds are defined as an array of values [*x0*, *x1*, …]. The first [generated density contour](#_density) corresponds to the area where the estimated density is greater than or equal to *x0*; the second contour corresponds to the area where the estimated density is greater than or equal to *x1*, and so on. Thus, there is exactly one generated MultiPolygon geometry object for each specified threshold value; the threshold value is exposed as <i>geometry</i>.value. The first value *x0* should typically be greater than zero.

If a *count* is specified instead of an array of *thresholds*, then approximately *count* uniformly-spaced nicely-rounded thresholds will be generated; see [d3.ticks](https://github.com/d3/d3-array/blob/master/README.md#ticks).

<a name="density_bandwidth" href="#density_bandwidth">#</a> <i>density</i>.<b>bandwidth</b>([<i>bandwidth</i>]) [<>](https://github.com/d3/d3-contour/blob/master/src/density.js "Source")

If *bandwidth* is specified, sets the bandwidth (the standard deviation) of the Gaussian kernel and returns the estimate. If *bandwidth* is not specified, returns the current bandwidth, which defaults to 20.4939…. The specified *bandwidth* is currently rounded to the nearest supported value by this implementation, and must be nonnegative.
