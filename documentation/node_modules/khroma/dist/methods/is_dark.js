"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var is_light_1 = require("./is_light");
/* IS DARK */
function isDark(color) {
    return !is_light_1.default(color);
}
/* EXPORT */
exports.default = isDark;
