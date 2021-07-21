"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var anonymous_1 = __importDefault(require("../tree/anonymous"));
var keyword_1 = __importDefault(require("../tree/keyword"));
function boolean(condition) {
    return condition ? keyword_1.default.True : keyword_1.default.False;
}
/**
 * Functions with evalArgs set to false are sent context
 * as the first argument.
 */
function If(context, condition, trueValue, falseValue) {
    return condition.eval(context) ? trueValue.eval(context)
        : (falseValue ? falseValue.eval(context) : new anonymous_1.default);
}
If.evalArgs = false;
exports.default = { boolean: boolean, 'if': If };
//# sourceMappingURL=boolean.js.map