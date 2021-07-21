"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var utils_1 = require("../utils");
var color_1 = require("../color");
var adjust_1 = require("./adjust");
/* SCALE */
function scale(color, channels) {
    var ch = color_1.default.parse(color), adjustments = {}, delta = function (amount, weight, max) { return weight > 0 ? (max - amount) * weight / 100 : amount * weight / 100; };
    for (var c in channels) {
        adjustments[c] = delta(ch[c], channels[c], utils_1.default.channel.max[c]);
    }
    return adjust_1.default(color, adjustments);
}
/* EXPORT */
exports.default = scale;
