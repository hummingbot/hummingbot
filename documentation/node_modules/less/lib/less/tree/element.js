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
var paren_1 = __importDefault(require("./paren"));
var combinator_1 = __importDefault(require("./combinator"));
var Element = /** @class */ (function (_super) {
    __extends(Element, _super);
    function Element(combinator, value, isVariable, index, currentFileInfo, visibilityInfo) {
        var _this = _super.call(this) || this;
        _this.combinator = combinator instanceof combinator_1.default ?
            combinator : new combinator_1.default(combinator);
        if (typeof value === 'string') {
            _this.value = value.trim();
        }
        else if (value) {
            _this.value = value;
        }
        else {
            _this.value = '';
        }
        _this.isVariable = isVariable;
        _this._index = index;
        _this._fileInfo = currentFileInfo;
        _this.copyVisibilityInfo(visibilityInfo);
        _this.setParent(_this.combinator, _this);
        return _this;
    }
    Element.prototype.accept = function (visitor) {
        var value = this.value;
        this.combinator = visitor.visit(this.combinator);
        if (typeof value === 'object') {
            this.value = visitor.visit(value);
        }
    };
    Element.prototype.eval = function (context) {
        return new Element(this.combinator, this.value.eval ? this.value.eval(context) : this.value, this.isVariable, this.getIndex(), this.fileInfo(), this.visibilityInfo());
    };
    Element.prototype.clone = function () {
        return new Element(this.combinator, this.value, this.isVariable, this.getIndex(), this.fileInfo(), this.visibilityInfo());
    };
    Element.prototype.genCSS = function (context, output) {
        output.add(this.toCSS(context), this.fileInfo(), this.getIndex());
    };
    Element.prototype.toCSS = function (context) {
        if (context === void 0) { context = {}; }
        var value = this.value;
        var firstSelector = context.firstSelector;
        if (value instanceof paren_1.default) {
            // selector in parens should not be affected by outer selector
            // flags (breaks only interpolated selectors - see #1973)
            context.firstSelector = true;
        }
        value = value.toCSS ? value.toCSS(context) : value;
        context.firstSelector = firstSelector;
        if (value === '' && this.combinator.value.charAt(0) === '&') {
            return '';
        }
        else {
            return this.combinator.toCSS(context) + value;
        }
    };
    return Element;
}(node_1.default));
Element.prototype.type = 'Element';
exports.default = Element;
//# sourceMappingURL=element.js.map