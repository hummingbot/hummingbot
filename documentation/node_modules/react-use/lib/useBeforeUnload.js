"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var react_1 = require("react");
var useBeforeUnload = function (enabled, message) {
    if (enabled === void 0) { enabled = true; }
    react_1.useEffect(function () {
        if (!enabled) {
            return;
        }
        var handler = function (event) {
            event.preventDefault();
            if (message) {
                event.returnValue = message;
            }
            return message;
        };
        window.addEventListener('beforeunload', handler);
        return function () { return window.removeEventListener('beforeunload', handler); };
    }, [message, enabled]);
};
exports.default = useBeforeUnload;
