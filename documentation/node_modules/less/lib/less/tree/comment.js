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
var debug_info_1 = __importDefault(require("./debug-info"));
var Comment = /** @class */ (function (_super) {
    __extends(Comment, _super);
    function Comment(value, isLineComment, index, currentFileInfo) {
        var _this = _super.call(this) || this;
        _this.value = value;
        _this.isLineComment = isLineComment;
        _this._index = index;
        _this._fileInfo = currentFileInfo;
        _this.allowRoot = true;
        return _this;
    }
    Comment.prototype.genCSS = function (context, output) {
        if (this.debugInfo) {
            output.add(debug_info_1.default(context, this), this.fileInfo(), this.getIndex());
        }
        output.add(this.value);
    };
    Comment.prototype.isSilent = function (context) {
        var isCompressed = context.compress && this.value[2] !== '!';
        return this.isLineComment || isCompressed;
    };
    return Comment;
}(node_1.default));
Comment.prototype.type = 'Comment';
exports.default = Comment;
//# sourceMappingURL=comment.js.map