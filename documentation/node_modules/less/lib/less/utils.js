"use strict";
var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    Object.defineProperty(o, k2, { enumerable: true, get: function() { return m[k]; } });
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (k !== "default" && Object.hasOwnProperty.call(mod, k)) __createBinding(result, mod, k);
    __setModuleDefault(result, mod);
    return result;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.flattenArray = exports.merge = exports.copyOptions = exports.defaults = exports.clone = exports.copyArray = exports.getLocation = void 0;
/* jshint proto: true */
var Constants = __importStar(require("./constants"));
function getLocation(index, inputStream) {
    var n = index + 1;
    var line = null;
    var column = -1;
    while (--n >= 0 && inputStream.charAt(n) !== '\n') {
        column++;
    }
    if (typeof index === 'number') {
        line = (inputStream.slice(0, index).match(/\n/g) || '').length;
    }
    return {
        line: line,
        column: column
    };
}
exports.getLocation = getLocation;
function copyArray(arr) {
    var i;
    var length = arr.length;
    var copy = new Array(length);
    for (i = 0; i < length; i++) {
        copy[i] = arr[i];
    }
    return copy;
}
exports.copyArray = copyArray;
function clone(obj) {
    var cloned = {};
    for (var prop in obj) {
        if (obj.hasOwnProperty(prop)) {
            cloned[prop] = obj[prop];
        }
    }
    return cloned;
}
exports.clone = clone;
function defaults(obj1, obj2) {
    var newObj = obj2 || {};
    if (!obj2._defaults) {
        newObj = {};
        var defaults_1 = __assign({}, obj1);
        newObj._defaults = defaults_1;
        var cloned = obj2 ? __assign({}, obj2) : {};
        Object.assign(newObj, defaults_1, cloned);
    }
    return newObj;
}
exports.defaults = defaults;
function copyOptions(obj1, obj2) {
    if (obj2 && obj2._defaults) {
        return obj2;
    }
    var opts = defaults(obj1, obj2);
    if (opts.strictMath) {
        opts.math = Constants.Math.STRICT_LEGACY;
    }
    // Back compat with changed relativeUrls option
    if (opts.relativeUrls) {
        opts.rewriteUrls = Constants.RewriteUrls.ALL;
    }
    if (typeof opts.math === 'string') {
        switch (opts.math.toLowerCase()) {
            case 'always':
                opts.math = Constants.Math.ALWAYS;
                break;
            case 'parens-division':
                opts.math = Constants.Math.PARENS_DIVISION;
                break;
            case 'strict':
            case 'parens':
                opts.math = Constants.Math.PARENS;
                break;
            case 'strict-legacy':
                opts.math = Constants.Math.STRICT_LEGACY;
        }
    }
    if (typeof opts.rewriteUrls === 'string') {
        switch (opts.rewriteUrls.toLowerCase()) {
            case 'off':
                opts.rewriteUrls = Constants.RewriteUrls.OFF;
                break;
            case 'local':
                opts.rewriteUrls = Constants.RewriteUrls.LOCAL;
                break;
            case 'all':
                opts.rewriteUrls = Constants.RewriteUrls.ALL;
                break;
        }
    }
    return opts;
}
exports.copyOptions = copyOptions;
function merge(obj1, obj2) {
    for (var prop in obj2) {
        if (obj2.hasOwnProperty(prop)) {
            obj1[prop] = obj2[prop];
        }
    }
    return obj1;
}
exports.merge = merge;
function flattenArray(arr, result) {
    if (result === void 0) { result = []; }
    for (var i = 0, length_1 = arr.length; i < length_1; i++) {
        var value = arr[i];
        if (Array.isArray(value)) {
            flattenArray(value, result);
        }
        else {
            if (value !== undefined) {
                result.push(value);
            }
        }
    }
    return result;
}
exports.flattenArray = flattenArray;
//# sourceMappingURL=utils.js.map