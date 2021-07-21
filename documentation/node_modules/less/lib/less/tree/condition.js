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
var Condition = /** @class */ (function (_super) {
    __extends(Condition, _super);
    function Condition(op, l, r, i, negate) {
        var _this = _super.call(this) || this;
        _this.op = op.trim();
        _this.lvalue = l;
        _this.rvalue = r;
        _this._index = i;
        _this.negate = negate;
        return _this;
    }
    Condition.prototype.accept = function (visitor) {
        this.lvalue = visitor.visit(this.lvalue);
        this.rvalue = visitor.visit(this.rvalue);
    };
    Condition.prototype.eval = function (context) {
        var result = (function (op, a, b) {
            switch (op) {
                case 'and': return a && b;
                case 'or': return a || b;
                default:
                    switch (node_1.default.compare(a, b)) {
                        case -1:
                            return op === '<' || op === '=<' || op === '<=';
                        case 0:
                            return op === '=' || op === '>=' || op === '=<' || op === '<=';
                        case 1:
                            return op === '>' || op === '>=';
                        default:
                            return false;
                    }
            }
        })(this.op, this.lvalue.eval(context), this.rvalue.eval(context));
        return this.negate ? !result : result;
    };
    return Condition;
}(node_1.default));
Condition.prototype.type = 'Condition';
exports.default = Condition;
//# sourceMappingURL=condition.js.map