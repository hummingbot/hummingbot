"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var react_1 = require("react");
var useUpdate_1 = require("./useUpdate");
var useGetSet = function (initialValue) {
    var state = react_1.useRef(initialValue);
    var update = useUpdate_1.default();
    var get = react_1.useCallback(function () { return state.current; }, []);
    var set = react_1.useCallback(function (value) {
        state.current = value;
        update();
    }, []);
    return [get, set];
};
exports.default = useGetSet;
