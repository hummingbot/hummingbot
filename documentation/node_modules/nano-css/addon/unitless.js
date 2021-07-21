'use strict';

var UNITLESS_NUMBER_PROPS = [
    'animation-iteration-count',
    'border-image-outset',
    'border-image-slice',
    'border-image-width',
    'box-flex',
    'box-flex-group',
    'box-ordinal-group',
    'column-count',
    'columns',
    'flex',
    'flex-grow',
    'flex-positive',
    'flex-shrink',
    'flex-negative',
    'flex-order',
    'grid-row',
    'grid-row-end',
    'grid-row-span',
    'grid-row-start',
    'grid-column',
    'grid-column-end',
    'grid-column-span',
    'grid-column-start',
    'font-weight',
    'line-clamp',
    'line-height',
    'opacity',
    'order',
    'orphans',
    'tabSize',
    'widows',
    'z-index',
    'zoom',

    // SVG-related properties
    'fill-opacity',
    'flood-opacity',
    'stop-opacity',
    'stroke-dasharray',
    'stroke-dashoffset',
    'stroke-miterlimit',
    'stroke-opacity',
    'stroke-width',
];

var unitlessCssProperties = {};

for (var i = 0; i < UNITLESS_NUMBER_PROPS.length; i++) {
    var prop = UNITLESS_NUMBER_PROPS[i];

    unitlessCssProperties[prop] = 1;
    unitlessCssProperties['-webkit-' + prop] = 1;
    unitlessCssProperties['-ms-' + prop] = 1;
    unitlessCssProperties['-moz-' + prop] = 1;
    unitlessCssProperties['-o-' + prop] = 1;
}

exports.addon = function (renderer) {
    var decl = renderer.decl;

    renderer.decl = function (prop, value) {
        var str = decl(prop, value);

        if (typeof value === 'number') {
            var pos = str.indexOf(':');
            var propKebab = str.substr(0, pos);

            if (!unitlessCssProperties[propKebab]) {
                return decl(prop, value + 'px');
            }
        }

        return str;
    };
};
