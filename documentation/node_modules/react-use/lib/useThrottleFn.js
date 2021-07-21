"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var react_1 = require("react");
var useUnmount_1 = require("./useUnmount");
var useThrottleFn = function (fn, ms, args) {
    if (ms === void 0) { ms = 200; }
    var _a = react_1.useState(null), state = _a[0], setState = _a[1];
    var timeout = react_1.useRef(null);
    var nextArgs = react_1.useRef(null);
    var hasNextArgs = react_1.useRef(false);
    react_1.useEffect(function () {
        if (!timeout.current) {
            setState(fn.apply(void 0, args));
            var timeoutCallback_1 = function () {
                if (hasNextArgs.current) {
                    hasNextArgs.current = false;
                    setState(fn.apply(void 0, nextArgs.current));
                    timeout.current = setTimeout(timeoutCallback_1, ms);
                }
                else {
                    timeout.current = null;
                }
            };
            timeout.current = setTimeout(timeoutCallback_1, ms);
        }
        else {
            nextArgs.current = args;
            hasNextArgs.current = true;
        }
    }, args);
    useUnmount_1.default(function () {
        clearTimeout(timeout.current);
    });
    return state;
};
exports.default = useThrottleFn;
