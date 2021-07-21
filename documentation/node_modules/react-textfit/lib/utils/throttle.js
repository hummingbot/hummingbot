"use strict";

Object.defineProperty(exports, "__esModule", {
    value: true
});
exports.default = throttle;
/**
 * Returns a new function that, when invoked, invokes `func` at most once per `wait` milliseconds.
 * Taken from https://github.com/component/throttle v1.0.0
 *
 * @param {Function} func Function to wrap.
 * @param {Number} wait Number of milliseconds that must elapse between `func` invocations.
 * @return {Function} A new function that wraps the `func` function passed in.
 */

function throttle(func, wait) {
    var ctx = void 0;
    var args = void 0;
    var rtn = void 0;
    var timeoutID = void 0;
    var last = 0;

    function call() {
        timeoutID = 0;
        last = +new Date();
        rtn = func.apply(ctx, args);
        ctx = null;
        args = null;
    }

    return function throttled() {
        ctx = this;
        args = arguments;
        var delta = new Date() - last;
        if (!timeoutID) {
            if (delta >= wait) call();else timeoutID = setTimeout(call, wait - delta);
        }
        return rtn;
    };
}