"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var change_1 = require("./change");
/* GRAYSCALE */
function grayscale(color) {
    return change_1.default(color, { s: 0 });
}
/* EXPORT */
exports.default = grayscale;
