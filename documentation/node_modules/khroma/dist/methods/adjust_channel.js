"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var utils_1 = require("../utils");
var color_1 = require("../color");
/* ADJUST CHANNEL */
function adjustChannel(color, channel, amount) {
    var channels = color_1.default.parse(color), amountCurrent = channels[channel], amountNext = utils_1.default.channel.clamp[channel](amountCurrent + amount);
    if (amountCurrent !== amountNext)
        channels[channel] = amountNext;
    return color_1.default.stringify(channels);
}
/* EXPORT */
exports.default = adjustChannel;
