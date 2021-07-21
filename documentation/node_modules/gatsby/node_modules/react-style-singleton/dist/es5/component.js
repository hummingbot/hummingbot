"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var hook_1 = require("./hook");
exports.styleSingleton = function () {
    var useStyle = hook_1.styleHookSingleton();
    var Sheet = function (_a) {
        var styles = _a.styles;
        useStyle(styles);
        return null;
    };
    return Sheet;
};
