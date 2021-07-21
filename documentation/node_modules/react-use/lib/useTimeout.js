"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var react_1 = require("react");
var useTimeout = function (ms) {
    if (ms === void 0) { ms = 0; }
    var _a = react_1.useState(false), ready = _a[0], setReady = _a[1];
    react_1.useEffect(function () {
        var timer = setTimeout(function () {
            setReady(true);
        }, ms);
        return function () {
            clearTimeout(timer);
        };
    }, [ms]);
    return ready;
};
exports.default = useTimeout;
