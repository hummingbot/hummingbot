"use strict";
var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
var __rest = (this && this.__rest) || function (s, e) {
    var t = {};
    for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0)
        t[p] = s[p];
    if (s != null && typeof Object.getOwnPropertySymbols === "function")
        for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
            if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i]))
                t[p[i]] = s[p[i]];
        }
    return t;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.toInvokeDefinition = exports.toInvokeSource = void 0;
var actions_1 = require("./actions");
function toInvokeSource(src) {
    if (typeof src === 'string') {
        var simpleSrc = { type: src };
        simpleSrc.toString = function () { return src; }; // v4 compat - TODO: remove in v5
        return simpleSrc;
    }
    return src;
}
exports.toInvokeSource = toInvokeSource;
function toInvokeDefinition(invokeConfig) {
    return __assign(__assign({ type: actions_1.actionTypes.invoke }, invokeConfig), { toJSON: function () {
            var onDone = invokeConfig.onDone, onError = invokeConfig.onError, invokeDef = __rest(invokeConfig, ["onDone", "onError"]);
            return __assign(__assign({}, invokeDef), { type: actions_1.actionTypes.invoke, src: toInvokeSource(invokeConfig.src) });
        } });
}
exports.toInvokeDefinition = toInvokeDefinition;
