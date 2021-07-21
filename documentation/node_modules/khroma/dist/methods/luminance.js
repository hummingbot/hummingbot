"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var utils_1 = require("../utils");
var color_1 = require("../color");
/* LUMINANCE */
//SOURCE: https://planetcalc.com/7779
function luminance(color) {
    var _a = color_1.default.parse(color), r = _a.r, g = _a.g, b = _a.b, luminance = .2126 * utils_1.default.channel.toLinear(r) + .7152 * utils_1.default.channel.toLinear(g) + .0722 * utils_1.default.channel.toLinear(b);
    return utils_1.default.lang.round(luminance);
}
/* EXPORT */
exports.default = luminance;
