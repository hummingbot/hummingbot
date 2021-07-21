"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var color_1 = require("../color");
var mix_1 = require("./mix");
/* INVERT */
function invert(color, weight) {
    if (weight === void 0) { weight = 100; }
    var inverse = color_1.default.parse(color);
    inverse.r = 255 - inverse.r;
    inverse.g = 255 - inverse.g;
    inverse.b = 255 - inverse.b;
    return mix_1.default(inverse, color, weight);
}
/* EXPORT */
exports.default = invert;
