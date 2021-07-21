"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var channel_1 = require("./channel");
/* BLUE */
function blue(color) {
    return channel_1.default(color, 'b');
}
/* EXPORT */
exports.default = blue;
