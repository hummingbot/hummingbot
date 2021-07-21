"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var math_helper_js_1 = __importDefault(require("./math-helper.js"));
var mathFunctions = {
    // name,  unit
    ceil: null,
    floor: null,
    sqrt: null,
    abs: null,
    tan: '',
    sin: '',
    cos: '',
    atan: 'rad',
    asin: 'rad',
    acos: 'rad'
};
for (var f in mathFunctions) {
    if (mathFunctions.hasOwnProperty(f)) {
        mathFunctions[f] = math_helper_js_1.default.bind(null, Math[f], mathFunctions[f]);
    }
}
mathFunctions.round = function (n, f) {
    var fraction = typeof f === 'undefined' ? 0 : f.value;
    return math_helper_js_1.default(function (num) { return num.toFixed(fraction); }, null, n);
};
exports.default = mathFunctions;
//# sourceMappingURL=math.js.map