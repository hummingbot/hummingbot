"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var react_1 = require("react");
var useEffectOnce = function (effect) {
    react_1.useEffect(effect, []);
};
exports.default = useEffectOnce;
