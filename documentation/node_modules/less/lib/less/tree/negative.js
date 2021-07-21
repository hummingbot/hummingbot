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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var node_1 = __importDefault(require("./node"));
var operation_1 = __importDefault(require("./operation"));
var dimension_1 = __importDefault(require("./dimension"));
var Negative = /** @class */ (function (_super) {
    __extends(Negative, _super);
    function Negative(node) {
        var _this = _super.call(this) || this;
        _this.value = node;
        return _this;
    }
    Negative.prototype.genCSS = function (context, output) {
        output.add('-');
        this.value.genCSS(context, output);
    };
    Negative.prototype.eval = function (context) {
        if (context.isMathOn()) {
            return (new operation_1.default('*', [new dimension_1.default(-1), this.value])).eval(context);
        }
        return new Negative(this.value.eval(context));
    };
    return Negative;
}(node_1.default));
Negative.prototype.type = 'Negative';
exports.default = Negative;
//# sourceMappingURL=negative.js.map