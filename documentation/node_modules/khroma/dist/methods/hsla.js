"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var utils_1 = require("../utils");
var reusable_1 = require("../channels/reusable");
var color_1 = require("../color");
/* HSLA */
function hsla(h, s, l, a) {
    if (a === void 0) { a = 1; }
    var channels = reusable_1.default.set({
        h: utils_1.default.channel.clamp.h(h),
        s: utils_1.default.channel.clamp.s(s),
        l: utils_1.default.channel.clamp.l(l),
        a: utils_1.default.channel.clamp.a(a)
    });
    return color_1.default.stringify(channels);
}
/* EXPORT */
exports.default = hsla;
