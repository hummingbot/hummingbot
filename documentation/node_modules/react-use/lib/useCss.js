"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var nano_css_1 = require("nano-css");
var cssom_1 = require("nano-css/addon/cssom");
var vcssom_1 = require("nano-css/addon/vcssom");
var cssToTree_1 = require("nano-css/addon/vcssom/cssToTree");
var react_1 = require("react");
var nano = nano_css_1.create();
cssom_1.addon(nano);
vcssom_1.addon(nano);
var counter = 0;
var useCss = function (css) {
    var className = react_1.useMemo(function () { return 'react-use-css-' + (counter++).toString(36); }, []);
    var sheet = react_1.useMemo(function () { return new nano.VSheet(); }, []);
    react_1.useLayoutEffect(function () {
        var tree = {};
        cssToTree_1.cssToTree(tree, css, '.' + className, '');
        sheet.diff(tree);
        return function () {
            sheet.diff({});
        };
    });
    return className;
};
exports.default = useCss;
