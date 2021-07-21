'use strict';

var units = {};
var unitList = 'px,cm,mm,in,pt,pc,em,ex,ch,rem,vw,vh,deg,vmin,vmax'.split(',');

function f (unit, val) {
    return val + unit;
}

for (var i = 0; i < unitList.length; i++) {
    var unit = unitList[i];

    units[unit] = f.bind(null, unit);
}

units.inch = function (val) {
    return val + 'in';
};

units.pct = function (val) {
    return val + '%';
};

exports.addon = function (renderer) {
    renderer.assign(renderer, units);
    renderer.units = units;
};
