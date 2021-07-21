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
var Attribute = /** @class */ (function (_super) {
    __extends(Attribute, _super);
    function Attribute(key, op, value) {
        var _this = _super.call(this) || this;
        _this.key = key;
        _this.op = op;
        _this.value = value;
        return _this;
    }
    Attribute.prototype.eval = function (context) {
        return new Attribute(this.key.eval ? this.key.eval(context) : this.key, this.op, (this.value && this.value.eval) ? this.value.eval(context) : this.value);
    };
    Attribute.prototype.genCSS = function (context, output) {
        output.add(this.toCSS(context));
    };
    Attribute.prototype.toCSS = function (context) {
        var value = this.key.toCSS ? this.key.toCSS(context) : this.key;
        if (this.op) {
            value += this.op;
            value += (this.value.toCSS ? this.value.toCSS(context) : this.value);
        }
        return "[" + value + "]";
    };
    return Attribute;
}(node_1.default));
Attribute.prototype.type = 'Attribute';
exports.default = Attribute;
//# sourceMappingURL=attribute.js.map