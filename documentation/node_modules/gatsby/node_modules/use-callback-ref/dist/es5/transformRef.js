"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var assignRef_1 = require("./assignRef");
var createRef_1 = require("./createRef");
function transformRef(ref, transformer) {
    return createRef_1.createCallbackRef(function (value) { return assignRef_1.assignRef(ref, transformer(value)); });
}
exports.transformRef = transformRef;
