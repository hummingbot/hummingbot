"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var react_1 = require("react");
var useGetSet_1 = require("./useGetSet");
var useCounter = function (initialValue) {
    if (initialValue === void 0) { initialValue = 0; }
    var _a = useGetSet_1.default(initialValue), get = _a[0], set = _a[1];
    var inc = react_1.useCallback(function (delta) {
        if (delta === void 0) { delta = 1; }
        return set(get() + delta);
    }, []);
    var dec = react_1.useCallback(function (delta) {
        if (delta === void 0) { delta = 1; }
        return inc(-delta);
    }, []);
    var reset = react_1.useCallback(function (value) {
        if (value === void 0) { value = initialValue; }
        initialValue = value;
        set(value);
    }, []);
    var actions = {
        inc: inc,
        dec: dec,
        get: get,
        set: set,
        reset: reset,
    };
    return [get(), actions];
};
exports.default = useCounter;
