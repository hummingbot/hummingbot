"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var react_1 = require("react");
var useRefMounted = function () {
    var refMounted = react_1.useRef(false);
    react_1.useEffect(function () {
        refMounted.current = true;
        return function () {
            refMounted.current = false;
        };
    }, []);
    return refMounted;
};
exports.default = useRefMounted;
