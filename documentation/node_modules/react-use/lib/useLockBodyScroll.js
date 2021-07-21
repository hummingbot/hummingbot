"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var react_1 = require("react");
var counter = 0;
var originalOverflow = null;
var lock = function () {
    originalOverflow = window.getComputedStyle(document.body).overflow;
    document.body.style.overflow = 'hidden';
};
var unlock = function () {
    document.body.style.overflow = originalOverflow;
    originalOverflow = null;
};
var increment = function () {
    counter++;
    if (counter === 1) {
        lock();
    }
};
var decrement = function () {
    counter--;
    if (counter === 0) {
        unlock();
    }
};
var useLockBodyScroll = function (enabled) {
    if (enabled === void 0) { enabled = true; }
    react_1.useEffect(function () { return (enabled ? (increment(), decrement) : undefined); }, [enabled]);
};
exports.default = useLockBodyScroll;
