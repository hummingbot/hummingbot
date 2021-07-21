"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var channel_1 = require("./channel");
/* SATURATION */
function saturation(color) {
    return channel_1.default(color, 's');
}
/* EXPORT */
exports.default = saturation;
