"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var luminance_1 = require("./luminance");
/* IS LIGHT */
function isLight(color) {
    return luminance_1.default(color) >= .5;
}
/* EXPORT */
exports.default = isLight;
