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
var color_1 = __importDefault(require("./color"));
var dimension_1 = __importDefault(require("./dimension"));
var Constants = __importStar(require("../constants"));
var MATH = Constants.Math;
var Operation = /** @class */ (function (_super) {
    __extends(Operation, _super);
    function Operation(op, operands, isSpaced) {
        var _this = _super.call(this) || this;
        _this.op = op.trim();
        _this.operands = operands;
        _this.isSpaced = isSpaced;
        return _this;
    }
    Operation.prototype.accept = function (visitor) {
        this.operands = visitor.visitArray(this.operands);
    };
    Operation.prototype.eval = function (context) {
        var a = this.operands[0].eval(context);
        var b = this.operands[1].eval(context);
        var op;
        if (context.isMathOn(this.op)) {
            op = this.op === './' ? '/' : this.op;
            if (a instanceof dimension_1.default && b instanceof color_1.default) {
                a = a.toColor();
            }
            if (b instanceof dimension_1.default && a instanceof color_1.default) {
                b = b.toColor();
            }
            if (!a.operate) {
                if (a instanceof Operation && a.op === '/' && context.math === MATH.PARENS_DIVISION) {
                    return new Operation(this.op, [a, b], this.isSpaced);
                }
                throw { type: 'Operation',
                    message: 'Operation on an invalid type' };
            }
            return a.operate(context, op, b);
        }
        else {
            return new Operation(this.op, [a, b], this.isSpaced);
        }
    };
    Operation.prototype.genCSS = function (context, output) {
        this.operands[0].genCSS(context, output);
        if (this.isSpaced) {
            output.add(' ');
        }
        output.add(this.op);
        if (this.isSpaced) {
            output.add(' ');
        }
        this.operands[1].genCSS(context, output);
    };
    return Operation;
}(node_1.default));
Operation.prototype.type = 'Operation';
exports.default = Operation;
//# sourceMappingURL=operation.js.map