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
var property_1 = __importDefault(require("./property"));
var Quoted = /** @class */ (function (_super) {
    __extends(Quoted, _super);
    function Quoted(str, content, escaped, index, currentFileInfo) {
        var _this = _super.call(this) || this;
        _this.escaped = (escaped == null) ? true : escaped;
        _this.value = content || '';
        _this.quote = str.charAt(0);
        _this._index = index;
        _this._fileInfo = currentFileInfo;
        _this.variableRegex = /@\{([\w-]+)\}/g;
        _this.propRegex = /\$\{([\w-]+)\}/g;
        _this.allowRoot = escaped;
        return _this;
    }
    Quoted.prototype.genCSS = function (context, output) {
        if (!this.escaped) {
            output.add(this.quote, this.fileInfo(), this.getIndex());
        }
        output.add(this.value);
        if (!this.escaped) {
            output.add(this.quote);
        }
    };
    Quoted.prototype.containsVariables = function () {
        return this.value.match(this.variableRegex);
    };
    Quoted.prototype.eval = function (context) {
        var that = this;
        var value = this.value;
        var variableReplacement = function (_, name) {
            var v = new variable_1.default("@" + name, that.getIndex(), that.fileInfo()).eval(context, true);
            return (v instanceof Quoted) ? v.value : v.toCSS();
        };
        var propertyReplacement = function (_, name) {
            var v = new property_1.default("$" + name, that.getIndex(), that.fileInfo()).eval(context, true);
            return (v instanceof Quoted) ? v.value : v.toCSS();
        };
        function iterativeReplace(value, regexp, replacementFnc) {
            var evaluatedValue = value;
            do {
                value = evaluatedValue.toString();
                evaluatedValue = value.replace(regexp, replacementFnc);
            } while (value !== evaluatedValue);
            return evaluatedValue;
        }
        value = iterativeReplace(value, this.variableRegex, variableReplacement);
        value = iterativeReplace(value, this.propRegex, propertyReplacement);
        return new Quoted(this.quote + value + this.quote, value, this.escaped, this.getIndex(), this.fileInfo());
    };
    Quoted.prototype.compare = function (other) {
        // when comparing quoted strings allow the quote to differ
        if (other.type === 'Quoted' && !this.escaped && !other.escaped) {
            return node_1.default.numericCompare(this.value, other.value);
        }
        else {
            return other.toCSS && this.toCSS() === other.toCSS() ? 0 : undefined;
        }
    };
    return Quoted;
}(node_1.default));
Quoted.prototype.type = 'Quoted';
exports.default = Quoted;
//# sourceMappingURL=quoted.js.map