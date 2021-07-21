# d3-brush

Brushing is the interactive specification a one- or two-dimensional selected region using a pointing gesture, such as by clicking and dragging the mouse. Brushing is often used to select discrete elements, such as dots in a scatterplot or files on a desktop. It can also be used to zoom-in to a region of interest, or to select continuous regions for [cross-filtering data](http://square.github.io/crossfilter/) or live histograms:

[<img alt="Mona Lisa Histogram" src="https://raw.githubusercontent.com/d3/d3-brush/master/img/mona-lisa.jpg" width="420" height="219">](http://bl.ocks.org/mbostock/0d20834e3d5a46138752f86b9b79727e)

The d3-brush module implements brushing for mouse and touch events using [SVG](https://www.w3.org/TR/SVG/). Click and drag on the brush selection to translate the selection. Click and drag on one of the selection handles to move the corresponding edge (or edges) of the selection. Click and drag on the invisible overlay to define a new brush selection, or click anywhere within the brushable region while holding down the META (⌘) key. Holding down the ALT (⌥) key while moving the brush causes it to reposition around its center, while holding down SPACE locks the current brush size, allowing only translation.

Brushes also support programmatic control. For example, you can listen to [*end* events](#brush-events), and then initiate a transition with [*brush*.move](#brush_move) to snap the brush selection to semantic boundaries:

[<img alt="Brush Snapping" src="https://raw.githubusercontent.com/d3/d3-brush/master/img/snapping.png" width="420" height="219">](http://bl.ocks.org/mbostock/6232537)

Or you can have the brush recenter when you click outside the current selection:

[<img alt="Click-to-Recenter" src="https://raw.githubusercontent.com/d3/d3-brush/master/img/recenter.jpg" width="420" height="219">](https://bl.ocks.org/mbostock/6498000)

## Installing

If you use NPM, `npm install d3-brush`. Otherwise, download the [latest release](https://github.com/d3/d3-brush/releases/latest). You can load as a [standalone library](https://d3js.org/d3-brush.v1.min.js) or as part of [D3](https://github.com/d3/d3). ES modules, AMD, CommonJS, and vanilla environments are supported. In vanilla, a `d3` global is exported:

```html
<script src="https://d3js.org/d3-color.v1.min.js"></script>
<script src="https://d3js.org/d3-dispatch.v1.min.js"></script>
<script src="https://d3js.org/d3-ease.v1.min.js"></script>
<script src="https://d3js.org/d3-interpolate.v1.min.js"></script>
<script src="https://d3js.org/d3-timer.v1.min.js"></script>
<script src="https://d3js.org/d3-selection.v1.min.js"></script>
<script src="https://d3js.org/d3-transition.v1.min.js"></script>
<script src="https://d3js.org/d3-drag.v1.min.js"></script>
<script src="https://d3js.org/d3-brush.v1.min.js"></script>
<script>

var brush = d3.brush();

</script>
```

## API Reference

<a href="#brush" name="brush">#</a> d3.<b>brush</b>() [<>](https://github.com/d3/d3-brush/blob/master/src/brush.js "Source")

Creates a new two-dimensional brush.

<a href="#brushX" name="brushX">#</a> d3.<b>brushX</b>() [<>](https://github.com/d3/d3-brush/blob/master/src/brush.js "Source")

Creates a new one-dimensional brush along the *x*-dimension.

<a href="#brushY" name="brushY">#</a> d3.<b>brushY</b>() [<>](https://github.com/d3/d3-brush/blob/master/src/brush.js "Source")

Creates a new one-dimensional brush along the *y*-dimension.

<a href="#_brush" name="_brush">#</a> <i>brush</i>(<i>group</i>) [<>](https://github.com/d3/d3-brush/blob/master/src/brush.js "Source")

Applies the brush to the specified *group*, which must be a [selection](https://github.com/d3/d3-selection) of SVG [G elements](https://www.w3.org/TR/SVG/struct.html#Groups). This function is typically not invoked directly, and is instead invoked via [*selection*.call](https://github.com/d3/d3-selection#selection_call). For example, to render a brush:

```js
svg.append("g")
    .attr("class", "brush")
    .call(d3.brush().on("brush", brushed));
```

Internally, the brush uses [*selection*.on](https://github.com/d3/d3-selection#selection_on) to bind the necessary event listeners for dragging. The listeners use the name `.brush`, so you can subsequently unbind the brush event listeners as follows:

```js
group.on(".brush", null);
```

The brush also creates the SVG elements necessary to display the brush selection and to receive input events for interaction. You can add, remove or modify these elements as desired to change the brush appearance; you can also apply stylesheets to modify the brush appearance. The structure of a two-dimensional brush is as follows:

```html
<g class="brush" fill="none" pointer-events="all" style="-webkit-tap-highlight-color: rgba(0, 0, 0, 0);">
  <rect class="overlay" pointer-events="all" cursor="crosshair" x="0" y="0" width="960" height="500"></rect>
  <rect class="selection" cursor="move" fill="#777" fill-opacity="0.3" stroke="#fff" shape-rendering="crispEdges" x="112" y="194" width="182" height="83"></rect>
  <rect class="handle handle--n" cursor="ns-resize" x="107" y="189" width="192" height="10"></rect>
  <rect class="handle handle--e" cursor="ew-resize" x="289" y="189" width="10" height="93"></rect>
  <rect class="handle handle--s" cursor="ns-resize" x="107" y="272" width="192" height="10"></rect>
  <rect class="handle handle--w" cursor="ew-resize" x="107" y="189" width="10" height="93"></rect>
  <rect class="handle handle--nw" cursor="nwse-resize" x="107" y="189" width="10" height="10"></rect>
  <rect class="handle handle--ne" cursor="nesw-resize" x="289" y="189" width="10" height="10"></rect>
  <rect class="handle handle--se" cursor="nwse-resize" x="289" y="272" width="10" height="10"></rect>
  <rect class="handle handle--sw" cursor="nesw-resize" x="107" y="272" width="10" height="10"></rect>
</g>
```

The overlay rect covers the brushable area defined by [*brush*.extent](#brush_extent). The selection rect covers the area defined by the current [brush selection](#brushSelection). The handle rects cover the edges and corners of the brush selection, allowing the corresponding value in the brush selection to be modified interactively. To modify the brush selection programmatically, use [*brush*.move](#brush_move).

<a href="#brush_move" name="brush_move">#</a> <i>brush</i>.<b>move</b>(<i>group</i>, <i>selection</i>) [<>](https://github.com/d3/d3-brush/blob/master/src/brush.js "Source")

Sets the active *selection* of the brush on the specified *group*, which must be a [selection](https://github.com/d3/d3-selection) or a [transition](https://github.com/d3/d3-transition) of SVG [G elements](https://www.w3.org/TR/SVG/struct.html#Groups). The *selection* must be defined as an array of numbers, or null to clear the brush selection. For a [two-dimensional brush](#brush), it must be defined as [[*x0*, *y0*], [*x1*, *y1*]], where *x0* is the minimum *x*-value, *y0* is the minimum *y*-value, *x1* is the maximum *x*-value, and *y1* is the maximum *y*-value. For an [*x*-brush](#brushX), it must be defined as [*x0*, *x1*]; for a [*y*-brush](#brushY), it must be defined as [*y0*, *y1*]. The selection may also be specified as a function which returns such an array; if a function, it is invoked for each selected element, being passed the current datum `d` and index `i`, with the `this` context as the current DOM element. The returned array defines the brush selection for that element.

<a href="#brush_clear" name="brush_clear">#</a> <i>brush</i>.<b>clear</b>(<i>group</i>) [<>](https://github.com/d3/d3-brush/blob/master/src/brush.js "Source")

An alias for [*brush*.move](#brush_move) with the null selection.

<a href="#brush_extent" name="brush_extent">#</a> <i>brush</i>.<b>extent</b>([<i>extent</i>]) [<>](https://github.com/d3/d3-brush/blob/master/src/brush.js "Source")

If *extent* is specified, sets the brushable extent to the specified array of points [[*x0*, *y0*], [*x1*, *y1*]], where [*x0*, *y0*] is the top-left corner and [*x1*, *y1*] is the bottom-right corner, and returns this brush. The *extent* may also be specified as a function which returns such an array; if a function, it is invoked for each selected element, being passed the current datum `d` and index `i`, with the `this` context as the current DOM element. If *extent* is not specified, returns the current extent accessor, which defaults to:

```js
function defaultExtent() {
  var svg = this.ownerSVGElement || this;
  if (svg.hasAttribute("viewBox")) {
    svg = svg.viewBox.baseVal;
    return [[svg.x, svg.y], [svg.x + svg.width, svg.y + svg.height]];
  }
  return [[0, 0], [svg.width.baseVal.value, svg.height.baseVal.value]];
}
```

This default implementation requires that the owner SVG element have a defined [viewBox](https://www.w3.org/TR/SVG/coords.html#ViewBoxAttribute), or [width](https://www.w3.org/TR/SVG/struct.html#SVGElementWidthAttribute) and [height](https://www.w3.org/TR/SVG/struct.html#SVGElementHeightAttribute) attributes. Alternatively, consider using [*element*.getBoundingClientRect](https://developer.mozilla.org/en-US/docs/Web/API/Element/getBoundingClientRect). (In Firefox, [*element*.clientWidth](https://developer.mozilla.org/en-US/docs/Web/API/Element/clientWidth) and [*element*.clientHeight](https://developer.mozilla.org/en-US/docs/Web/API/Element/clientHeight) is zero for SVG elements!)

The brush extent determines the size of the invisible overlay and also constrains the brush selection; the brush selection cannot go outside the brush extent.

<a href="#brush_filter" name="brush_filter">#</a> <i>brush</i>.<b>filter</b>([<i>filter</i>]) [<>](https://github.com/d3/d3-brush/blob/master/src/brush.js "Source")

If *filter* is specified, sets the filter to the specified function and returns the brush. If *filter* is not specified, returns the current filter, which defaults to:

```js
function filter() {
  return !d3.event.ctrlKey && !d3.event.button;
}
```

If the filter returns falsey, the initiating event is ignored and no brush gesture is started. Thus, the filter determines which input events are ignored. The default filter ignores mousedown events on secondary buttons, since those buttons are typically intended for other purposes, such as the context menu.

<a href="#brush_touchable" name="brush_touchable">#</a> <i>brush</i>.<b>touchable</b>([<i>touchable</i>]) [<>](https://github.com/d3/d3-brush/blob/master/src/brush.js "Source")

If *touchable* is specified, sets the touch support detector to the specified function and returns the brush. If *touchable* is not specified, returns the current touch support detector, which defaults to:

```js
function touchable() {
  return navigator.maxTouchPoints || ("ontouchstart" in this);
}
```

Touch event listeners are only registered if the detector returns truthy for the corresponding element when the brush is [applied](#_brush). The default detector works well for most browsers that are capable of touch input, but not all; Chrome’s mobile device emulator, for example, fails detection.

<a href="#brush_keyModifiers" name="brush_keyModifiers">#</a> <i>brush</i>.<b>keyModifiers</b>([<i>modifiers</i>]) [<>](https://github.com/d3/d3-brush/blob/master/src/brush.js "Source")

If *modifiers* is specified, sets whether the brush listens to key events during brushing and returns the brush. If *modifiers* is not specified, returns the current behavior, which defaults to true.

<a href="#brush_handleSize" name="brush_handleSize">#</a> <i>brush</i>.<b>handleSize</b>([<i>size</i>]) [<>](https://github.com/d3/d3-brush/blob/master/src/brush.js "Source")

If *size* is specified, sets the size of the brush handles to the specified number and returns the brush. If *size* is not specified, returns the current handle size, which defaults to six. This method must be called before [applying the brush](#_brush) to a selection; changing the handle size does not affect brushes that were previously rendered.

<a href="#brush_on" name="brush_on">#</a> <i>brush</i>.<b>on</b>(<i>typenames</i>[, <i>listener</i>]) [<>](https://github.com/d3/d3-brush/blob/master/src/brush.js "Source")

If *listener* is specified, sets the event *listener* for the specified *typenames* and returns the brush. If an event listener was already registered for the same type and name, the existing listener is removed before the new listener is added. If *listener* is null, removes the current event listeners for the specified *typenames*, if any. If *listener* is not specified, returns the first currently-assigned listener matching the specified *typenames*, if any. When a specified event is dispatched, each *listener* will be invoked with the same context and arguments as [*selection*.on](https://github.com/d3/d3-selection#selection_on) listeners: the current datum `d` and index `i`, with the `this` context as the current DOM element.

The *typenames* is a string containing one or more *typename* separated by whitespace. Each *typename* is a *type*, optionally followed by a period (`.`) and a *name*, such as `brush.foo` and `brush.bar`; the name allows multiple listeners to be registered for the same *type*. The *type* must be one of the following:

* `start` - at the start of a brush gesture, such as on mousedown.
* `brush` - when the brush moves, such as on mousemove.
* `end` - at the end of a brush gesture, such as on mouseup.

See [*dispatch*.on](https://github.com/d3/d3-dispatch#dispatch_on) and [Brush Events](#brush-events) for more.

<a href="#brushSelection" name="brushSelection">#</a> d3.<b>brushSelection</b>(<i>node</i>) [<>](https://github.com/d3/d3-brush/blob/master/src/brush.js "Source")

Returns the current brush selection for the specified *node*. Internally, an element’s brush state is stored as *element*.\_\_brush; however, you should use this method rather than accessing it directly. If the given *node* has no selection, returns null. Otherwise, the *selection* is defined as an array of numbers. For a [two-dimensional brush](#brush), it is [[*x0*, *y0*], [*x1*, *y1*]], where *x0* is the minimum *x*-value, *y0* is the minimum *y*-value, *x1* is the maximum *x*-value, and *y1* is the maximum *y*-value. For an [*x*-brush](#brushX), it is [*x0*, *x1*]; for a [*y*-brush](#brushY), it is [*y0*, *y1*].

### Brush Events

When a [brush event listener](#brush_on) is invoked, [d3.event](https://github.com/d3/d3-selection#event) is set to the current brush event. The *event* object exposes several fields:

* `target` - the associated [brush behavior](#brush).
* `type` - the string “start”, “brush” or “end”; see [*brush*.on](#brush_on).
* `selection` - the current [brush selection](#brushSelection).
* `sourceEvent` - the underlying input event, such as mousemove or touchmove.
