"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var utils_1 = require("../utils");
var color_1 = require("../color");
/* CHANGE */
function change(color, channels) {
    var ch = color_1.default.parse(color);
    for (var c in channels) {
        ch[c] = utils_1.default.channel.clamp[c](channels[c]);
    }
    return color_1.default.stringify(ch);
}
/* EXPORT */
exports.default = change;
