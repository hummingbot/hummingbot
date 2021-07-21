"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var react_1 = require("react");
var useTitle = function (title) {
    react_1.useEffect(function () {
        document.title = title;
    }, [title]);
};
exports.default = useTitle;
