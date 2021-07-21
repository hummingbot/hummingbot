"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var react_1 = require("react");
var isEqual = require("react-fast-compare");
var isPrimitive = function (val) { return val !== Object(val); };
var useDeepCompareEffect = function (effect, deps) {
    if (process.env.NODE_ENV !== 'production') {
        if (!deps || !deps.length) {
            console.warn('`useDeepCompareEffect` should not be used with no dependencies. Use React.useEffect instead.');
        }
        if (deps.every(isPrimitive)) {
            console.warn('`useDeepCompareEffect` should not be used with dependencies that are all primitive values. Use React.useEffect instead.');
        }
    }
    var ref = react_1.useRef(undefined);
    if (!isEqual(deps, ref.current)) {
        ref.current = deps;
    }
    react_1.useEffect(effect, ref.current);
};
exports.default = useDeepCompareEffect;
