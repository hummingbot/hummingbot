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
var Value = /** @class */ (function (_super) {
    __extends(Value, _super);
    function Value(value) {
        var _this = _super.call(this) || this;
        if (!value) {
            throw new Error('Value requires an array argument');
        }
        if (!Array.isArray(value)) {
            _this.value = [value];
        }
        else {
            _this.value = value;
        }
        return _this;
    }
    Value.prototype.accept = function (visitor) {
        if (this.value) {
            this.value = visitor.visitArray(this.value);
        }
    };
    Value.prototype.eval = function (context) {
        if (this.value.length === 1) {
            return this.value[0].eval(context);
        }
        else {
            return new Value(this.value.map(function (v) { return v.eval(context); }));
        }
    };
    Value.prototype.genCSS = function (context, output) {
        var i;
        for (i = 0; i < this.value.length; i++) {
            this.value[i].genCSS(context, output);
            if (i + 1 < this.value.length) {
                output.add((context && context.compress) ? ',' : ', ');
            }
        }
    };
    return Value;
}(node_1.default));
Value.prototype.type = 'Value';
exports.default = Value;
//# sourceMappingURL=value.js.map