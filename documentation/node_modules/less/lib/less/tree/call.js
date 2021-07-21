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
var anonymous_1 = __importDefault(require("./anonymous"));
var function_caller_1 = __importDefault(require("../functions/function-caller"));
//
// A function call node.
//
var Call = /** @class */ (function (_super) {
    __extends(Call, _super);
    function Call(name, args, index, currentFileInfo) {
        var _this = _super.call(this) || this;
        _this.name = name;
        _this.args = args;
        _this.calc = name === 'calc';
        _this._index = index;
        _this._fileInfo = currentFileInfo;
        return _this;
    }
    Call.prototype.accept = function (visitor) {
        if (this.args) {
            this.args = visitor.visitArray(this.args);
        }
    };
    //
    // When evaluating a function call,
    // we either find the function in the functionRegistry,
    // in which case we call it, passing the  evaluated arguments,
    // if this returns null or we cannot find the function, we
    // simply print it out as it appeared originally [2].
    //
    // The reason why we evaluate the arguments, is in the case where
    // we try to pass a variable to a function, like: `saturate(@color)`.
    // The function should receive the value, not the variable.
    //
    Call.prototype.eval = function (context) {
        var _this = this;
        /**
         * Turn off math for calc(), and switch back on for evaluating nested functions
         */
        var currentMathContext = context.mathOn;
        context.mathOn = !this.calc;
        if (this.calc || context.inCalc) {
            context.enterCalc();
        }
        var exitCalc = function () {
            if (_this.calc || context.inCalc) {
                context.exitCalc();
            }
            context.mathOn = currentMathContext;
        };
        var result;
        var funcCaller = new function_caller_1.default(this.name, context, this.getIndex(), this.fileInfo());
        if (funcCaller.isValid()) {
            try {
                result = funcCaller.call(this.args);
                exitCalc();
            }
            catch (e) {
                if (e.hasOwnProperty('line') && e.hasOwnProperty('column')) {
                    throw e;
                }
                throw {
                    type: e.type || 'Runtime',
                    message: "error evaluating function `" + this.name + "`" + (e.message ? ": " + e.message : ''),
                    index: this.getIndex(),
                    filename: this.fileInfo().filename,
                    line: e.lineNumber,
                    column: e.columnNumber
                };
            }
            if (result !== null && result !== undefined) {
                // Results that that are not nodes are cast as Anonymous nodes
                // Falsy values or booleans are returned as empty nodes
                if (!(result instanceof node_1.default)) {
                    if (!result || result === true) {
                        result = new anonymous_1.default(null);
                    }
                    else {
                        result = new anonymous_1.default(result.toString());
                    }
                }
                result._index = this._index;
                result._fileInfo = this._fileInfo;
                return result;
            }
        }
        var args = this.args.map(function (a) { return a.eval(context); });
        exitCalc();
        return new Call(this.name, args, this.getIndex(), this.fileInfo());
    };
    Call.prototype.genCSS = function (context, output) {
        output.add(this.name + "(", this.fileInfo(), this.getIndex());
        for (var i = 0; i < this.args.length; i++) {
            this.args[i].genCSS(context, output);
            if (i + 1 < this.args.length) {
                output.add(', ');
            }
        }
        output.add(')');
    };
    return Call;
}(node_1.default));
Call.prototype.type = 'Call';
exports.default = Call;
//# sourceMappingURL=call.js.map