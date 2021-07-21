"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var keyword_1 = __importDefault(require("../tree/keyword"));
var detached_ruleset_1 = __importDefault(require("../tree/detached-ruleset"));
var dimension_1 = __importDefault(require("../tree/dimension"));
var color_1 = __importDefault(require("../tree/color"));
var quoted_1 = __importDefault(require("../tree/quoted"));
var anonymous_1 = __importDefault(require("../tree/anonymous"));
var url_1 = __importDefault(require("../tree/url"));
var operation_1 = __importDefault(require("../tree/operation"));
var isa = function (n, Type) { return (n instanceof Type) ? keyword_1.default.True : keyword_1.default.False; };
var isunit = function (n, unit) {
    if (unit === undefined) {
        throw { type: 'Argument', message: 'missing the required second argument to isunit.' };
    }
    unit = typeof unit.value === 'string' ? unit.value : unit;
    if (typeof unit !== 'string') {
        throw { type: 'Argument', message: 'Second argument to isunit should be a unit or a string.' };
    }
    return (n instanceof dimension_1.default) && n.unit.is(unit) ? keyword_1.default.True : keyword_1.default.False;
};
exports.default = {
    isruleset: function (n) {
        return isa(n, detached_ruleset_1.default);
    },
    iscolor: function (n) {
        return isa(n, color_1.default);
    },
    isnumber: function (n) {
        return isa(n, dimension_1.default);
    },
    isstring: function (n) {
        return isa(n, quoted_1.default);
    },
    iskeyword: function (n) {
        return isa(n, keyword_1.default);
    },
    isurl: function (n) {
        return isa(n, url_1.default);
    },
    ispixel: function (n) {
        return isunit(n, 'px');
    },
    ispercentage: function (n) {
        return isunit(n, '%');
    },
    isem: function (n) {
        return isunit(n, 'em');
    },
    isunit: isunit,
    unit: function (val, unit) {
        if (!(val instanceof dimension_1.default)) {
            throw { type: 'Argument', message: "the first argument to unit must be a number" + (val instanceof operation_1.default ? '. Have you forgotten parenthesis?' : '') };
        }
        if (unit) {
            if (unit instanceof keyword_1.default) {
                unit = unit.value;
            }
            else {
                unit = unit.toCSS();
            }
        }
        else {
            unit = '';
        }
        return new dimension_1.default(val.value, unit);
    },
    'get-unit': function (n) {
        return new anonymous_1.default(n.unit);
    }
};
//# sourceMappingURL=types.js.map