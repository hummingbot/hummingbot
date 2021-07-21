"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var color_1 = require("../color");
var change_1 = require("./change");
/* ADJUST */
function adjust(color, channels) {
    var ch = color_1.default.parse(color), changes = {};
    for (var c in channels) {
        if (!channels[c])
            continue;
        changes[c] = ch[c] + channels[c];
    }
    return change_1.default(color, changes);
}
/* EXPORT */
exports.default = adjust;
