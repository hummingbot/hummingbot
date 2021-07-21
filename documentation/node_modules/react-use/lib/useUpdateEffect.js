"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var react_1 = require("react");
var useUpdateEffect = function (effect, deps) {
    var isInitialMount = react_1.useRef(true);
    react_1.useEffect(isInitialMount.current
        ? function () {
            isInitialMount.current = false;
        }
        : effect, deps);
};
exports.default = useUpdateEffect;
