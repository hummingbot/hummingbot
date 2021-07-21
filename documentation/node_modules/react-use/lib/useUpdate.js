"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var react_1 = require("react");
var useUpdate = function () {
    var _a = react_1.useState(0), setState = _a[1];
    return function () { return setState(function (cnt) { return cnt + 1; }); };
};
exports.default = useUpdate;
