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
var variable_1 = __importDefault(require("./variable"));
var ruleset_1 = __importDefault(require("./ruleset"));
var detached_ruleset_1 = __importDefault(require("./detached-ruleset"));
var less_error_1 = __importDefault(require("../less-error"));
var VariableCall = /** @class */ (function (_super) {
    __extends(VariableCall, _super);
    function VariableCall(variable, index, currentFileInfo) {
        var _this = _super.call(this) || this;
        _this.variable = variable;
        _this._index = index;
        _this._fileInfo = currentFileInfo;
        _this.allowRoot = true;
        return _this;
    }
    VariableCall.prototype.eval = function (context) {
        var rules;
        var detachedRuleset = new variable_1.default(this.variable, this.getIndex(), this.fileInfo()).eval(context);
        var error = new less_error_1.default({ message: "Could not evaluate variable call " + this.variable });
        if (!detachedRuleset.ruleset) {
            if (detachedRuleset.rules) {
                rules = detachedRuleset;
            }
            else if (Array.isArray(detachedRuleset)) {
                rules = new ruleset_1.default('', detachedRuleset);
            }
            else if (Array.isArray(detachedRuleset.value)) {
                rules = new ruleset_1.default('', detachedRuleset.value);
            }
            else {
                throw error;
            }
            detachedRuleset = new detached_ruleset_1.default(rules);
        }
        if (detachedRuleset.ruleset) {
            return detachedRuleset.callEval(context);
        }
        throw error;
    };
    return VariableCall;
}(node_1.default));
VariableCall.prototype.type = 'VariableCall';
exports.default = VariableCall;
//# sourceMappingURL=variable-call.js.map