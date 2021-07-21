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
var Anonymous = /** @class */ (function (_super) {
    __extends(Anonymous, _super);
    function Anonymous(value, index, currentFileInfo, mapLines, rulesetLike, visibilityInfo) {
        var _this = _super.call(this) || this;
        _this.value = value;
        _this._index = index;
        _this._fileInfo = currentFileInfo;
        _this.mapLines = mapLines;
        _this.rulesetLike = (typeof rulesetLike === 'undefined') ? false : rulesetLike;
        _this.allowRoot = true;
        _this.copyVisibilityInfo(visibilityInfo);
        return _this;
    }
    Anonymous.prototype.eval = function () {
        return new Anonymous(this.value, this._index, this._fileInfo, this.mapLines, this.rulesetLike, this.visibilityInfo());
    };
    Anonymous.prototype.compare = function (other) {
        return other.toCSS && this.toCSS() === other.toCSS() ? 0 : undefined;
    };
    Anonymous.prototype.isRulesetLike = function () {
        return this.rulesetLike;
    };
    Anonymous.prototype.genCSS = function (context, output) {
        this.nodeVisible = Boolean(this.value);
        if (this.nodeVisible) {
            output.add(this.value, this._fileInfo, this._index, this.mapLines);
        }
    };
    return Anonymous;
}(node_1.default));
Anonymous.prototype.type = 'Anonymous';
exports.default = Anonymous;
//# sourceMappingURL=anonymous.js.map