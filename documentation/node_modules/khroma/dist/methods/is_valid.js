"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var color_1 = require("../color");
/* IS VALID */
function isValid(color) {
    try {
        color_1.default.parse(color);
        return true;
    }
    catch (_a) {
        return false;
    }
}
/* EXPORT */
exports.default = isValid;
