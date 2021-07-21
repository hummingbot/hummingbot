"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var react_1 = require("react");
var util_1 = require("./util");
var defaultTarget = util_1.isClient ? window : null;
var useEvent = function (name, handler, target, options) {
    if (target === void 0) { target = defaultTarget; }
    react_1.useEffect(function () {
        if (!handler) {
            return;
        }
        if (!target) {
            return;
        }
        var fn = target.addEventListener || target.on;
        fn.call(target, name, handler, options);
        return function () {
            var cleanFn = target.removeEventListener || target.off;
            cleanFn.call(target, name, handler, options);
        };
    }, [name, handler, target, JSON.stringify(options)]);
};
exports.default = useEvent;
