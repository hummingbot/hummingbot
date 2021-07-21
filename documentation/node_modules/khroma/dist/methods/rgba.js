"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var utils_1 = require("../utils");
var reusable_1 = require("../channels/reusable");
var color_1 = require("../color");
var change_1 = require("./change");
function rgba(r, g, b, a) {
    if (b === void 0) { b = 0; }
    if (a === void 0) { a = 1; }
    if (typeof r !== 'number')
        return change_1.default(r, { a: g });
    var channels = reusable_1.default.set({
        r: utils_1.default.channel.clamp.r(r),
        g: utils_1.default.channel.clamp.g(g),
        b: utils_1.default.channel.clamp.b(b),
        a: utils_1.default.channel.clamp.a(a)
    });
    return color_1.default.stringify(channels);
}
/* EXPORT */
exports.default = rgba;
