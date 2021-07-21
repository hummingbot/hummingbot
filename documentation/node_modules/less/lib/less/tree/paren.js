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
var Paren = /** @class */ (function (_super) {
    __extends(Paren, _super);
    function Paren(node) {
        var _this = _super.call(this) || this;
        _this.value = node;
        return _this;
    }
    Paren.prototype.genCSS = function (context, output) {
        output.add('(');
        this.value.genCSS(context, output);
        output.add(')');
    };
    Paren.prototype.eval = function (context) {
        return new Paren(this.value.eval(context));
    };
    return Paren;
}(node_1.default));
Paren.prototype.type = 'Paren';
exports.default = Paren;
//# sourceMappingURL=paren.js.map