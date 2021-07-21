"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var React = require("react");
var singleton_1 = require("./singleton");
exports.styleHookSingleton = function () {
    var sheet = singleton_1.stylesheetSingleton();
    return function (styles) {
        React.useEffect(function () {
            sheet.add(styles);
            return function () {
                sheet.remove();
            };
        }, []);
    };
};
