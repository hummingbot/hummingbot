"use strict";

Object.defineProperty(exports, "__esModule", {
    value: true
});
exports.default = uniqueId;
var uid = 0;

function uniqueId() {
    return uid++;
}