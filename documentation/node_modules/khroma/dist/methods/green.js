"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var channel_1 = require("./channel");
/* GREEN */
function green(color) {
    return channel_1.default(color, 'g');
}
/* EXPORT */
exports.default = green;
