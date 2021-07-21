"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var channel_1 = require("./channel");
/* LIGHTNESS */
function lightness(color) {
    return channel_1.default(color, 'l');
}
/* EXPORT */
exports.default = lightness;
