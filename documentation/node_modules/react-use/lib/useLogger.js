"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var useEffectOnce_1 = require("./useEffectOnce");
var useUpdateEffect_1 = require("./useUpdateEffect");
var useLogger = function (componentName) {
    var rest = [];
    for (var _i = 1; _i < arguments.length; _i++) {
        rest[_i - 1] = arguments[_i];
    }
    useEffectOnce_1.default(function () {
        console.log.apply(console, [componentName + " mounted"].concat(rest));
        return function () { return console.log(componentName + " unmounted"); };
    });
    useUpdateEffect_1.default(function () {
        console.log.apply(console, [componentName + " updated"].concat(rest));
    });
};
exports.default = useLogger;
