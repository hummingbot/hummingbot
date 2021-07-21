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
var element_1 = __importDefault(require("./element"));
var less_error_1 = __importDefault(require("../less-error"));
var Selector = /** @class */ (function (_super) {
    __extends(Selector, _super);
    function Selector(elements, extendList, condition, index, currentFileInfo, visibilityInfo) {
        var _this = _super.call(this) || this;
        _this.extendList = extendList;
        _this.condition = condition;
        _this.evaldCondition = !condition;
        _this._index = index;
        _this._fileInfo = currentFileInfo;
        _this.elements = _this.getElements(elements);
        _this.mixinElements_ = undefined;
        _this.copyVisibilityInfo(visibilityInfo);
        _this.setParent(_this.elements, _this);
        return _this;
    }
    Selector.prototype.accept = function (visitor) {
        if (this.elements) {
            this.elements = visitor.visitArray(this.elements);
        }
        if (this.extendList) {
            this.extendList = visitor.visitArray(this.extendList);
        }
        if (this.condition) {
            this.condition = visitor.visit(this.condition);
        }
    };
    Selector.prototype.createDerived = function (elements, extendList, evaldCondition) {
        elements = this.getElements(elements);
        var newSelector = new Selector(elements, extendList || this.extendList, null, this.getIndex(), this.fileInfo(), this.visibilityInfo());
        newSelector.evaldCondition = (evaldCondition != null) ? evaldCondition : this.evaldCondition;
        newSelector.mediaEmpty = this.mediaEmpty;
        return newSelector;
    };
    Selector.prototype.getElements = function (els) {
        if (!els) {
            return [new element_1.default('', '&', false, this._index, this._fileInfo)];
        }
        if (typeof els === 'string') {
            this.parse.parseNode(els, ['selector'], this._index, this._fileInfo, function (err, result) {
                if (err) {
                    throw new less_error_1.default({
                        index: err.index,
                        message: err.message
                    }, this.parse.imports, this._fileInfo.filename);
                }
                els = result[0].elements;
            });
        }
        return els;
    };
    Selector.prototype.createEmptySelectors = function () {
        var el = new element_1.default('', '&', false, this._index, this._fileInfo);
        var sels = [new Selector([el], null, null, this._index, this._fileInfo)];
        sels[0].mediaEmpty = true;
        return sels;
    };
    Selector.prototype.match = function (other) {
        var elements = this.elements;
        var len = elements.length;
        var olen;
        var i;
        other = other.mixinElements();
        olen = other.length;
        if (olen === 0 || len < olen) {
            return 0;
        }
        else {
            for (i = 0; i < olen; i++) {
                if (elements[i].value !== other[i]) {
                    return 0;
                }
            }
        }
        return olen; // return number of matched elements
    };
    Selector.prototype.mixinElements = function () {
        if (this.mixinElements_) {
            return this.mixinElements_;
        }
        var elements = this.elements.map(function (v) { return v.combinator.value + (v.value.value || v.value); }).join('').match(/[,&#\*\.\w-]([\w-]|(\\.))*/g);
        if (elements) {
            if (elements[0] === '&') {
                elements.shift();
            }
        }
        else {
            elements = [];
        }
        return (this.mixinElements_ = elements);
    };
    Selector.prototype.isJustParentSelector = function () {
        return !this.mediaEmpty &&
            this.elements.length === 1 &&
            this.elements[0].value === '&' &&
            (this.elements[0].combinator.value === ' ' || this.elements[0].combinator.value === '');
    };
    Selector.prototype.eval = function (context) {
        var evaldCondition = this.condition && this.condition.eval(context);
        var elements = this.elements;
        var extendList = this.extendList;
        elements = elements && elements.map(function (e) { return e.eval(context); });
        extendList = extendList && extendList.map(function (extend) { return extend.eval(context); });
        return this.createDerived(elements, extendList, evaldCondition);
    };
    Selector.prototype.genCSS = function (context, output) {
        var i;
        var element;
        if ((!context || !context.firstSelector) && this.elements[0].combinator.value === '') {
            output.add(' ', this.fileInfo(), this.getIndex());
        }
        for (i = 0; i < this.elements.length; i++) {
            element = this.elements[i];
            element.genCSS(context, output);
        }
    };
    Selector.prototype.getIsOutput = function () {
        return this.evaldCondition;
    };
    return Selector;
}(node_1.default));
Selector.prototype.type = 'Selector';
exports.default = Selector;
//# sourceMappingURL=selector.js.map