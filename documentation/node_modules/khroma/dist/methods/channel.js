"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var utils_1 = require("../utils");
var color_1 = require("../color");
/* CHANNEL */
function channel(color, channel) {
    return utils_1.default.lang.round(color_1.default.parse(color)[channel]);
}
/* EXPORT */
exports.default = channel;
