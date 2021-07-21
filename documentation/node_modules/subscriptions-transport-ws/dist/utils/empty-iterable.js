"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.createEmptyIterable = void 0;
var iterall_1 = require("iterall");
exports.createEmptyIterable = function () {
    var _a;
    return _a = {
            next: function () {
                return Promise.resolve({ value: undefined, done: true });
            },
            return: function () {
                return Promise.resolve({ value: undefined, done: true });
            },
            throw: function (e) {
                return Promise.reject(e);
            }
        },
        _a[iterall_1.$$asyncIterator] = function () {
            return this;
        },
        _a;
};
//# sourceMappingURL=empty-iterable.js.map