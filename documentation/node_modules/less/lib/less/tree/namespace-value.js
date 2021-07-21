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
var selector_1 = __importDefault(require("./selector"));
var NamespaceValue = /** @class */ (function (_super) {
    __extends(NamespaceValue, _super);
    function NamespaceValue(ruleCall, lookups, index, fileInfo) {
        var _this = _super.call(this) || this;
        _this.value = ruleCall;
        _this.lookups = lookups;
        _this._index = index;
        _this._fileInfo = fileInfo;
        return _this;
    }
    NamespaceValue.prototype.eval = function (context) {
        var i;
        var j;
        var name;
        var rules = this.value.eval(context);
        for (i = 0; i < this.lookups.length; i++) {
            name = this.lookups[i];
            /**
             * Eval'd DRs return rulesets.
             * Eval'd mixins return rules, so let's make a ruleset if we need it.
             * We need to do this because of late parsing of values
             */
            if (Array.isArray(rules)) {
                rules = new ruleset_1.default([new selector_1.default()], rules);
            }
            if (name === '') {
                rules = rules.lastDeclaration();
            }
            else if (name.charAt(0) === '@') {
                if (name.charAt(1) === '@') {
                    name = "@" + new variable_1.default(name.substr(1)).eval(context).value;
                }
                if (rules.variables) {
                    rules = rules.variable(name);
                }
                if (!rules) {
                    throw { type: 'Name', message: "variable " + name + " not found", filename: this.fileInfo().filename,
                        index: this.getIndex() };
                }
            }
            else {
                if (name.substring(0, 2) === '$@') {
                    name = "$" + new variable_1.default(name.substr(1)).eval(context).value;
                }
                else {
                    name = name.charAt(0) === '$' ? name : "$" + name;
                }
                if (rules.properties) {
                    rules = rules.property(name);
                }
                if (!rules) {
                    throw { type: 'Name', message: "property \"" + name.substr(1) + "\" not found", filename: this.fileInfo().filename,
                        index: this.getIndex() };
                }
                // Properties are an array of values, since a ruleset can have multiple props.
                // We pick the last one (the "cascaded" value)
                rules = rules[rules.length - 1];
            }
            if (rules.value) {
                rules = rules.eval(context).value;
            }
            if (rules.ruleset) {
                rules = rules.ruleset.eval(context);
            }
        }
        return rules;
    };
    return NamespaceValue;
}(node_1.default));
NamespaceValue.prototype.type = 'NamespaceValue';
exports.default = NamespaceValue;
//# sourceMappingURL=namespace-value.js.map