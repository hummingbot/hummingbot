"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var color_1 = require("../color");
var rgba_1 = require("./rgba");
/* MIX */
//SOURCE: https://github.com/sass/dart-sass/blob/7457d2e9e7e623d9844ffd037a070cf32d39c348/lib/src/functions/color.dart#L718-L756
function mix(color1, color2, weight) {
    if (weight === void 0) { weight = 50; }
    var _a = color_1.default.parse(color1), r1 = _a.r, g1 = _a.g, b1 = _a.b, a1 = _a.a, _b = color_1.default.parse(color2), r2 = _b.r, g2 = _b.g, b2 = _b.b, a2 = _b.a, weightScale = weight / 100, weightNormalized = (weightScale * 2) - 1, alphaDelta = a1 - a2, weight1combined = ((weightNormalized * alphaDelta) === -1) ? weightNormalized : (weightNormalized + alphaDelta) / (1 + weightNormalized * alphaDelta), weight1 = (weight1combined + 1) / 2, weight2 = 1 - weight1, r = (r1 * weight1) + (r2 * weight2), g = (g1 * weight1) + (g2 * weight2), b = (b1 * weight1) + (b2 * weight2), a = (a1 * weightScale) + (a2 * (1 - weightScale));
    return rgba_1.default(r, g, b, a);
}
/* EXPORT */
exports.default = mix;
