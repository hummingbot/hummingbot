import { useMemo } from 'react';
var createMemo = function (fn) { return function () {
    var args = [];
    for (var _i = 0; _i < arguments.length; _i++) {
        args[_i] = arguments[_i];
    }
    return useMemo(function () { return fn.apply(void 0, args); }, args);
}; };
export default createMemo;
