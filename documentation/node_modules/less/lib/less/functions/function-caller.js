"use strict";
var __spreadArrays = (this && this.__spreadArrays) || function () {
    for (var s = 0, i = 0, il = arguments.length; i < il; i++) s += arguments[i].length;
    for (var r = Array(s), k = 0, i = 0; i < il; i++)
        for (var a = arguments[i], j = 0, jl = a.length; j < jl; j++, k++)
            r[k] = a[j];
    return r;
};
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var expression_1 = __importDefault(require("../tree/expression"));
var functionCaller = /** @class */ (function () {
    function functionCaller(name, context, index, currentFileInfo) {
        this.name = name.toLowerCase();
        this.index = index;
        this.context = context;
        this.currentFileInfo = currentFileInfo;
        this.func = context.frames[0].functionRegistry.get(this.name);
    }
    functionCaller.prototype.isValid = function () {
        return Boolean(this.func);
    };
    functionCaller.prototype.call = function (args) {
        var _this = this;
        var evalArgs = this.func.evalArgs;
        if (evalArgs !== false) {
            args = args.map(function (a) { return a.eval(_this.context); });
        }
        // This code is terrible and should be replaced as per this issue...
        // https://github.com/less/less.js/issues/2477
        if (Array.isArray(args)) {
            args = args.filter(function (item) {
                if (item.type === 'Comment') {
                    return false;
                }
                return true;
            })
                .map(function (item) {
                if (item.type === 'Expression') {
                    var subNodes = item.value.filter(function (item) {
                        if (item.type === 'Comment') {
                            return false;
                        }
                        return true;
                    });
                    if (subNodes.length === 1) {
                        return subNodes[0];
                    }
                    else {
                        return new expression_1.default(subNodes);
                    }
                }
                return item;
            });
        }
        if (evalArgs === false) {
            return this.func.apply(this, __spreadArrays([this.context], args));
        }
        return this.func.apply(this, args);
    };
    return functionCaller;
}());
exports.default = functionCaller;
//# sourceMappingURL=function-caller.js.map