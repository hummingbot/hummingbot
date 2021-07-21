"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var iterall_1 = require("iterall");
exports.withFilter = function (asyncIteratorFn, filterFn) {
    return function (rootValue, args, context, info) {
        var _a;
        var asyncIterator = asyncIteratorFn(rootValue, args, context, info);
        var getNextPromise = function () {
            return asyncIterator
                .next()
                .then(function (payload) {
                if (payload.done === true) {
                    return payload;
                }
                return Promise.resolve(filterFn(payload.value, args, context, info))
                    .catch(function () { return false; })
                    .then(function (filterResult) {
                    if (filterResult === true) {
                        return payload;
                    }
                    return getNextPromise();
                });
            });
        };
        return _a = {
                next: function () {
                    return getNextPromise();
                },
                return: function () {
                    return asyncIterator.return();
                },
                throw: function (error) {
                    return asyncIterator.throw(error);
                }
            },
            _a[iterall_1.$$asyncIterator] = function () {
                return this;
            },
            _a;
    };
};
//# sourceMappingURL=with-filter.js.map