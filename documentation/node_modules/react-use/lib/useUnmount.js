"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var useEffectOnce_1 = require("./useEffectOnce");
var useUnmount = function (fn) {
    useEffectOnce_1.default(function () { return fn; });
};
exports.default = useUnmount;
