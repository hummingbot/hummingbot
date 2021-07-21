"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var writeText = require("copy-to-clipboard");
var react_1 = require("react");
var useRefMounted_1 = require("./useRefMounted");
var useSetState_1 = require("./useSetState");
var useCopyToClipboard = function () {
    var mounted = useRefMounted_1.default();
    var _a = useSetState_1.default({
        value: undefined,
        error: undefined,
        noUserInteraction: true,
    }), state = _a[0], setState = _a[1];
    var copyToClipboard = react_1.useCallback(function (value) {
        try {
            if (process.env.NODE_ENV === 'development') {
                if (typeof value !== 'string') {
                    console.error("Cannot copy typeof " + typeof value + " to clipboard, must be a string");
                }
            }
            var noUserInteraction = writeText(value);
            if (!mounted.current) {
                return;
            }
            setState({
                value: value,
                error: undefined,
                noUserInteraction: noUserInteraction,
            });
        }
        catch (error) {
            if (!mounted.current) {
                return;
            }
            setState({
                value: undefined,
                error: error,
                noUserInteraction: true,
            });
        }
    }, []);
    return [state, copyToClipboard];
};
exports.default = useCopyToClipboard;
