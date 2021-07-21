"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var React = require("react");
var react_style_singleton_1 = require("react-style-singleton");
var utils_1 = require("./utils");
var constants_1 = require("./constants");
var Style = react_style_singleton_1.styleSingleton();
var getStyles = function (_a, allowRelative, gapMode, important) {
    var left = _a.left, top = _a.top, right = _a.right, gap = _a.gap;
    if (gapMode === void 0) { gapMode = 'margin'; }
    return "\n  ." + constants_1.noScrollbarsClassName + " {\n   overflow: hidden " + important + ";\n   padding-right: " + gap + "px " + important + ";\n  }\n  body {\n    overflow: hidden " + important + ";\n    " + [
        allowRelative && "position: relative " + important + ";",
        gapMode === 'margin' && "\n    padding-left: " + left + "px;\n    padding-top: " + top + "px;\n    padding-right: " + right + "px;\n    margin-left:0;\n    margin-top:0;\n    margin-right: " + gap + "px " + important + ";\n    ",
        gapMode === 'padding' && "padding-right: " + gap + "px " + important + ";",
    ].filter(Boolean).join('') + "\n  }\n  \n  ." + constants_1.zeroRightClassName + " {\n    right: " + gap + "px " + important + ";\n  }\n  \n  ." + constants_1.fullWidthClassName + " {\n    margin-right: " + gap + "px " + important + ";\n  }\n  \n  ." + constants_1.zeroRightClassName + " ." + constants_1.zeroRightClassName + " {\n    right: 0 " + important + ";\n  }\n  \n  ." + constants_1.fullWidthClassName + " ." + constants_1.fullWidthClassName + " {\n    margin-right: 0 " + important + ";\n  }\n";
};
exports.RemoveScrollBar = function (props) {
    var _a = React.useState(utils_1.getGapWidth(props.gapMode)), gap = _a[0], setGap = _a[1];
    React.useEffect(function () {
        setGap(utils_1.getGapWidth(props.gapMode));
    }, [props.gapMode]);
    var noRelative = props.noRelative, noImportant = props.noImportant, _b = props.gapMode, gapMode = _b === void 0 ? 'margin' : _b;
    return React.createElement(Style, { styles: getStyles(gap, !noRelative, gapMode, !noImportant ? "!important" : '') });
};
