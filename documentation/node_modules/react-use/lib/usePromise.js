"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var react_1 = require("react");
var useRefMounted_1 = require("./useRefMounted");
var usePromise = function () {
    var refMounted = useRefMounted_1.default();
    return react_1.useCallback(function (promise) {
        return new Promise(function (resolve, reject) {
            var onValue = function (value) {
                if (refMounted.current) {
                    resolve(value);
                }
            };
            var onError = function (error) {
                if (refMounted.current) {
                    reject(error);
                }
            };
            promise.then(onValue, onError);
        });
    }, []);
};
exports.default = usePromise;
