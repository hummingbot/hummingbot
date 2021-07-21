"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var dimension_1 = __importDefault(require("../tree/dimension"));
var anonymous_1 = __importDefault(require("../tree/anonymous"));
var math_helper_js_1 = __importDefault(require("./math-helper.js"));
var minMax = function (isMin, args) {
    args = Array.prototype.slice.call(args);
    switch (args.length) {
        case 0: throw { type: 'Argument', message: 'one or more arguments required' };
    }
    var i; // key is the unit.toString() for unified Dimension values,
    var j;
    var current;
    var currentUnified;
    var referenceUnified;
    var unit;
    var unitStatic;
    var unitClone;
    var // elems only contains original argument values.
    order = [];
    var values = {};
    // value is the index into the order array.
    for (i = 0; i < args.length; i++) {
        current = args[i];
        if (!(current instanceof dimension_1.default)) {
            if (Array.isArray(args[i].value)) {
                Array.prototype.push.apply(args, Array.prototype.slice.call(args[i].value));
            }
            continue;
        }
        currentUnified = current.unit.toString() === '' && unitClone !== undefined ? new dimension_1.default(current.value, unitClone).unify() : current.unify();
        unit = currentUnified.unit.toString() === '' && unitStatic !== undefined ? unitStatic : currentUnified.unit.toString();
        unitStatic = unit !== '' && unitStatic === undefined || unit !== '' && order[0].unify().unit.toString() === '' ? unit : unitStatic;
        unitClone = unit !== '' && unitClone === undefined ? current.unit.toString() : unitClone;
        j = values[''] !== undefined && unit !== '' && unit === unitStatic ? values[''] : values[unit];
        if (j === undefined) {
            if (unitStatic !== undefined && unit !== unitStatic) {
                throw { type: 'Argument', message: 'incompatible types' };
            }
            values[unit] = order.length;
            order.push(current);
            continue;
        }
        referenceUnified = order[j].unit.toString() === '' && unitClone !== undefined ? new dimension_1.default(order[j].value, unitClone).unify() : order[j].unify();
        if (isMin && currentUnified.value < referenceUnified.value ||
            !isMin && currentUnified.value > referenceUnified.value) {
            order[j] = current;
        }
    }
    if (order.length == 1) {
        return order[0];
    }
    args = order.map(function (a) { return a.toCSS(this.context); }).join(this.context.compress ? ',' : ', ');
    return new anonymous_1.default((isMin ? 'min' : 'max') + "(" + args + ")");
};
exports.default = {
    min: function () {
        var args = [];
        for (var _i = 0; _i < arguments.length; _i++) {
            args[_i] = arguments[_i];
        }
        return minMax(true, args);
    },
    max: function () {
        var args = [];
        for (var _i = 0; _i < arguments.length; _i++) {
            args[_i] = arguments[_i];
        }
        return minMax(false, args);
    },
    convert: function (val, unit) {
        return val.convertTo(unit.value);
    },
    pi: function () {
        return new dimension_1.default(Math.PI);
    },
    mod: function (a, b) {
        return new dimension_1.default(a.value % b.value, a.unit);
    },
    pow: function (x, y) {
        if (typeof x === 'number' && typeof y === 'number') {
            x = new dimension_1.default(x);
            y = new dimension_1.default(y);
        }
        else if (!(x instanceof dimension_1.default) || !(y instanceof dimension_1.default)) {
            throw { type: 'Argument', message: 'arguments must be numbers' };
        }
        return new dimension_1.default(Math.pow(x.value, y.value), x.unit);
    },
    percentage: function (n) {
        var result = math_helper_js_1.default(function (num) { return num * 100; }, '%', n);
        return result;
    }
};
//# sourceMappingURL=number.js.map