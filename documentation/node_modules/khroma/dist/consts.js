"use strict";
/* IMPORT */
Object.defineProperty(exports, "__esModule", { value: true });
var utils_1 = require("./utils");
/* CONSTS */
var DEC2HEX = {};
exports.DEC2HEX = DEC2HEX;
for (var i = 0; i <= 255; i++)
    DEC2HEX[i] = utils_1.default.unit.dec2hex(i); // Populating dynamically, striking a balance between code size and performance
