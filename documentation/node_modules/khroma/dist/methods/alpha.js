"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var channel_1 = require("./channel");
/* ALPHA */
function alpha(color) {
    return channel_1.default(color, 'a');
}
/* EXPORT */
exports.default = alpha;
