"use strict";
var __extends = (this && this.__extends) || (function () {
    var extendStatics = function (d, b) {
        extendStatics = Object.setPrototypeOf ||
            ({ __proto__: [] } instanceof Array && function (d, b) { d.__proto__ = b; }) ||
            function (d, b) { for (var p in b) if (b.hasOwnProperty(p)) d[p] = b[p]; };
        return extendStatics(d, b);
    };
    return function (d, b) {
        extendStatics(d, b);
        function __() { this.constructor = d; }
        d.prototype = b === null ? Object.create(b) : (__.prototype = b.prototype, new __());
    };
})();
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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var node_1 = __importDefault(require("./node"));
var unit_conversions_1 = __importDefault(require("../data/unit-conversions"));
var utils = __importStar(require("../utils"));
var Unit = /** @class */ (function (_super) {
    __extends(Unit, _super);
    function Unit(numerator, denominator, backupUnit) {
        var _this = _super.call(this) || this;
        _this.numerator = numerator ? utils.copyArray(numerator).sort() : [];
        _this.denominator = denominator ? utils.copyArray(denominator).sort() : [];
        if (backupUnit) {
            _this.backupUnit = backupUnit;
        }
        else if (numerator && numerator.length) {
            _this.backupUnit = numerator[0];
        }
        return _this;
    }
    Unit.prototype.clone = function () {
        return new Unit(utils.copyArray(this.numerator), utils.copyArray(this.denominator), this.backupUnit);
    };
    Unit.prototype.genCSS = function (context, output) {
        // Dimension checks the unit is singular and throws an error if in strict math mode.
        var strictUnits = context && context.strictUnits;
        if (this.numerator.length === 1) {
            output.add(this.numerator[0]); // the ideal situation
        }
        else if (!strictUnits && this.backupUnit) {
            output.add(this.backupUnit);
        }
        else if (!strictUnits && this.denominator.length) {
            output.add(this.denominator[0]);
        }
    };
    Unit.prototype.toString = function () {
        var i;
        var returnStr = this.numerator.join('*');
        for (i = 0; i < this.denominator.length; i++) {
            returnStr += "/" + this.denominator[i];
        }
        return returnStr;
    };
    Unit.prototype.compare = function (other) {
        return this.is(other.toString()) ? 0 : undefined;
    };
    Unit.prototype.is = function (unitString) {
        return this.toString().toUpperCase() === unitString.toUpperCase();
    };
    Unit.prototype.isLength = function () {
        return RegExp('^(px|em|ex|ch|rem|in|cm|mm|pc|pt|ex|vw|vh|vmin|vmax)$', 'gi').test(this.toCSS());
    };
    Unit.prototype.isEmpty = function () {
        return this.numerator.length === 0 && this.denominator.length === 0;
    };
    Unit.prototype.isSingular = function () {
        return this.numerator.length <= 1 && this.denominator.length === 0;
    };
    Unit.prototype.map = function (callback) {
        var i;
        for (i = 0; i < this.numerator.length; i++) {
            this.numerator[i] = callback(this.numerator[i], false);
        }
        for (i = 0; i < this.denominator.length; i++) {
            this.denominator[i] = callback(this.denominator[i], true);
        }
    };
    Unit.prototype.usedUnits = function () {
        var group;
        var result = {};
        var mapUnit;
        var groupName;
        mapUnit = function (atomicUnit) {
            /* jshint loopfunc:true */
            if (group.hasOwnProperty(atomicUnit) && !result[groupName]) {
                result[groupName] = atomicUnit;
            }
            return atomicUnit;
        };
        for (groupName in unit_conversions_1.default) {
            if (unit_conversions_1.default.hasOwnProperty(groupName)) {
                group = unit_conversions_1.default[groupName];
                this.map(mapUnit);
            }
        }
        return result;
    };
    Unit.prototype.cancel = function () {
        var counter = {};
        var atomicUnit;
        var i;
        for (i = 0; i < this.numerator.length; i++) {
            atomicUnit = this.numerator[i];
            counter[atomicUnit] = (counter[atomicUnit] || 0) + 1;
        }
        for (i = 0; i < this.denominator.length; i++) {
            atomicUnit = this.denominator[i];
            counter[atomicUnit] = (counter[atomicUnit] || 0) - 1;
        }
        this.numerator = [];
        this.denominator = [];
        for (atomicUnit in counter) {
            if (counter.hasOwnProperty(atomicUnit)) {
                var count = counter[atomicUnit];
                if (count > 0) {
                    for (i = 0; i < count; i++) {
                        this.numerator.push(atomicUnit);
                    }
                }
                else if (count < 0) {
                    for (i = 0; i < -count; i++) {
                        this.denominator.push(atomicUnit);
                    }
                }
            }
        }
        this.numerator.sort();
        this.denominator.sort();
    };
    return Unit;
}(node_1.default));
Unit.prototype.type = 'Unit';
exports.default = Unit;
//# sourceMappingURL=unit.js.map