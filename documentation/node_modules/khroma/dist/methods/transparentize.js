"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var adjust_channel_1 = require("./adjust_channel");
/* TRANSPARENTIZE */
function transparentize(color, amount) {
    return adjust_channel_1.default(color, 'a', -amount);
}
/* EXPORT */
exports.default = transparentize;
