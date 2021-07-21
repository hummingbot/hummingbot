"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var adjust_channel_1 = require("./adjust_channel");
/* DARKEN */
function darken(color, amount) {
    return adjust_channel_1.default(color, 'l', -amount);
}
/* EXPORT */
exports.default = darken;
