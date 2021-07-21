"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var channel_1 = require("./channel");
/* RED */
function red(color) {
    return channel_1.default(color, 'r');
}
/* EXPORT */
exports.default = red;
