'use strict';

Object.defineProperty(exports, '__esModule', { value: true });

var d3Array = require('d3-array');
var d3Axis = require('d3-axis');
var d3Brush = require('d3-brush');
var d3Chord = require('d3-chord');
var d3Collection = require('d3-collection');
var d3Color = require('d3-color');
var d3Contour = require('d3-contour');
var d3Dispatch = require('d3-dispatch');
var d3Drag = require('d3-drag');
var d3Dsv = require('d3-dsv');
var d3Ease = require('d3-ease');
var d3Fetch = require('d3-fetch');
var d3Force = require('d3-force');
var d3Format = require('d3-format');
var d3Geo = require('d3-geo');
var d3Hierarchy = require('d3-hierarchy');
var d3Interpolate = require('d3-interpolate');
var d3Path = require('d3-path');
var d3Polygon = require('d3-polygon');
var d3Quadtree = require('d3-quadtree');
var d3Random = require('d3-random');
var d3Scale = require('d3-scale');
var d3ScaleChromatic = require('d3-scale-chromatic');
var d3Selection = require('d3-selection');
var d3Shape = require('d3-shape');
var d3Time = require('d3-time');
var d3TimeFormat = require('d3-time-format');
var d3Timer = require('d3-timer');
var d3Transition = require('d3-transition');
var d3Voronoi = require('d3-voronoi');
var d3Zoom = require('d3-zoom');

var version = "5.16.0";

Object.keys(d3Array).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Array[k];
		}
	});
});
Object.keys(d3Axis).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Axis[k];
		}
	});
});
Object.keys(d3Brush).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Brush[k];
		}
	});
});
Object.keys(d3Chord).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Chord[k];
		}
	});
});
Object.keys(d3Collection).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Collection[k];
		}
	});
});
Object.keys(d3Color).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Color[k];
		}
	});
});
Object.keys(d3Contour).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Contour[k];
		}
	});
});
Object.keys(d3Dispatch).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Dispatch[k];
		}
	});
});
Object.keys(d3Drag).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Drag[k];
		}
	});
});
Object.keys(d3Dsv).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Dsv[k];
		}
	});
});
Object.keys(d3Ease).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Ease[k];
		}
	});
});
Object.keys(d3Fetch).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Fetch[k];
		}
	});
});
Object.keys(d3Force).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Force[k];
		}
	});
});
Object.keys(d3Format).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Format[k];
		}
	});
});
Object.keys(d3Geo).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Geo[k];
		}
	});
});
Object.keys(d3Hierarchy).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Hierarchy[k];
		}
	});
});
Object.keys(d3Interpolate).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Interpolate[k];
		}
	});
});
Object.keys(d3Path).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Path[k];
		}
	});
});
Object.keys(d3Polygon).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Polygon[k];
		}
	});
});
Object.keys(d3Quadtree).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Quadtree[k];
		}
	});
});
Object.keys(d3Random).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Random[k];
		}
	});
});
Object.keys(d3Scale).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Scale[k];
		}
	});
});
Object.keys(d3ScaleChromatic).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3ScaleChromatic[k];
		}
	});
});
Object.keys(d3Selection).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Selection[k];
		}
	});
});
Object.keys(d3Shape).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Shape[k];
		}
	});
});
Object.keys(d3Time).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Time[k];
		}
	});
});
Object.keys(d3TimeFormat).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3TimeFormat[k];
		}
	});
});
Object.keys(d3Timer).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Timer[k];
		}
	});
});
Object.keys(d3Transition).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Transition[k];
		}
	});
});
Object.keys(d3Voronoi).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Voronoi[k];
		}
	});
});
Object.keys(d3Zoom).forEach(function (k) {
	if (k !== 'default') Object.defineProperty(exports, k, {
		enumerable: true,
		get: function () {
			return d3Zoom[k];
		}
	});
});
exports.version = version;
