"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var useEffectOnce_1 = require("./useEffectOnce");
var useMount = function (fn) {
    useEffectOnce_1.default(function () {
        fn();
    });
};
exports.default = useMount;
