"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var dimension_1 = __importDefault(require("../tree/dimension"));
var MathHelper = function (fn, unit, n) {
    if (!(n instanceof dimension_1.default)) {
        throw { type: 'Argument', message: 'argument must be a number' };
    }
    if (unit == null) {
        unit = n.unit;
    }
    else {
        n = n.unify();
    }
    return new dimension_1.default(fn(parseFloat(n.value)), unit);
};
exports.default = MathHelper;
//# sourceMappingURL=math-helper.js.map