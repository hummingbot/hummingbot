"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var channel_1 = require("./channel");
/* HUE */
function hue(color) {
    return channel_1.default(color, 'h');
}
/* EXPORT */
exports.default = hue;
