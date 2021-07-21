"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var adjust_channel_1 = require("./adjust_channel");
/* COMPLEMENT */
function complement(color) {
    return adjust_channel_1.default(color, 'h', 180);
}
/* EXPORT */
exports.default = complement;
