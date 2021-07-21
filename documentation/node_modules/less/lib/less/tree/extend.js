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
var selector_1 = __importDefault(require("./selector"));
var Extend = /** @class */ (function (_super) {
    __extends(Extend, _super);
    function Extend(selector, option, index, currentFileInfo, visibilityInfo) {
        var _this = _super.call(this) || this;
        _this.selector = selector;
        _this.option = option;
        _this.object_id = Extend.next_id++;
        _this.parent_ids = [_this.object_id];
        _this._index = index;
        _this._fileInfo = currentFileInfo;
        _this.copyVisibilityInfo(visibilityInfo);
        _this.allowRoot = true;
        switch (option) {
            case 'all':
                _this.allowBefore = true;
                _this.allowAfter = true;
                break;
            default:
                _this.allowBefore = false;
                _this.allowAfter = false;
                break;
        }
        _this.setParent(_this.selector, _this);
        return _this;
    }
    Extend.prototype.accept = function (visitor) {
        this.selector = visitor.visit(this.selector);
    };
    Extend.prototype.eval = function (context) {
        return new Extend(this.selector.eval(context), this.option, this.getIndex(), this.fileInfo(), this.visibilityInfo());
    };
    Extend.prototype.clone = function (context) {
        return new Extend(this.selector, this.option, this.getIndex(), this.fileInfo(), this.visibilityInfo());
    };
    // it concatenates (joins) all selectors in selector array
    Extend.prototype.findSelfSelectors = function (selectors) {
        var selfElements = [];
        var i;
        var selectorElements;
        for (i = 0; i < selectors.length; i++) {
            selectorElements = selectors[i].elements;
            // duplicate the logic in genCSS function inside the selector node.
            // future TODO - move both logics into the selector joiner visitor
            if (i > 0 && selectorElements.length && selectorElements[0].combinator.value === '') {
                selectorElements[0].combinator.value = ' ';
            }
            selfElements = selfElements.concat(selectors[i].elements);
        }
        this.selfSelectors = [new selector_1.default(selfElements)];
        this.selfSelectors[0].copyVisibilityInfo(this.visibilityInfo());
    };
    return Extend;
}(node_1.default));
Extend.next_id = 0;
Extend.prototype.type = 'Extend';
exports.default = Extend;
//# sourceMappingURL=extend.js.map