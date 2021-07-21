# d3-polygon

This module provides a few basic geometric operations for two-dimensional polygons. Each polygon is represented as an array of two-element arrays [​[<i>x1</i>, <i>y1</i>], [<i>x2</i>, <i>y2</i>], …], and may either be closed (wherein the first and last point are the same) or open (wherein they are not). Typically polygons are in counterclockwise order, assuming a coordinate system where the origin ⟨0,0⟩ is in the top-left corner.

## Installing

If you use NPM, `npm install d3-polygon`. Otherwise, download the [latest release](https://github.com/d3/d3-polygon/releases/latest). You can also load directly from [d3js.org](https://d3js.org), either as a [standalone library](https://d3js.org/d3-polygon.v1.min.js) or as part of [D3](https://github.com/d3/d3). AMD, CommonJS, and vanilla environments are supported. In vanilla, a `d3` global is exported:

```html
<script src="https://d3js.org/d3-polygon.v1.min.js"></script>
<script>

var hull = d3.polygonHull(points);

</script>
```

## API Reference

<a href="#polygonArea" name="polygonArea">#</a> d3.<b>polygonArea</b>(<i>polygon</i>) [<>](https://github.com/d3/d3-polygon/blob/master/src/area.js#L1 "Source Code")

Returns the signed area of the specified *polygon*. If the vertices of the polygon are in counterclockwise order (assuming a coordinate system where the origin ⟨0,0⟩ is in the top-left corner), the returned area is positive; otherwise it is negative, or zero.

<a href="#polygonCentroid" name="polygonCentroid">#</a> d3.<b>polygonCentroid</b>(<i>polygon</i>) [<>](https://github.com/d3/d3-polygon/blob/master/src/centroid.js#L1 "Source Code")

Returns the [centroid](https://en.wikipedia.org/wiki/Centroid) of the specified *polygon*.

<a href="#polygonHull" name="polygonHull">#</a> d3.<b>polygonHull</b>(<i>points</i>) [<>](https://github.com/d3/d3-polygon/blob/master/src/hull.js#L23 "Source Code")

<a href="http://bl.ocks.org/mbostock/6f14f7b7f267a85f7cdc"><img src="https://raw.githubusercontent.com/d3/d3-polygon/master/img/hull.png" width="250" height="250"></a>

Returns the [convex hull](https://en.wikipedia.org/wiki/Convex_hull) of the specified *points* using [Andrew’s monotone chain algorithm](http://en.wikibooks.org/wiki/Algorithm_Implementation/Geometry/Convex_hull/Monotone_chain). The returned hull is represented as an array containing a subset of the input *points* arranged in counterclockwise order. Returns null if *points* has fewer than three elements.

<a href="#polygonContains" name="polygonContains">#</a> d3.<b>polygonContains</b>(<i>polygon</i>, <i>point</i>) [<>](https://github.com/d3/d3-polygon/blob/master/src/contains.js#L1 "Source Code")

Returns true if and only if the specified *point* is inside the specified *polygon*.

<a href="#polygonLength" name="polygonLength">#</a> d3.<b>polygonLength</b>(<i>polygon</i>) [<>](https://github.com/d3/d3-polygon/blob/master/src/length.js#L1 "Source Code")

Returns the length of the perimeter of the specified *polygon*.
