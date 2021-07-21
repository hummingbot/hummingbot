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
var URL = /** @class */ (function (_super) {
    __extends(URL, _super);
    function URL(val, index, currentFileInfo, isEvald) {
        var _this = _super.call(this) || this;
        _this.value = val;
        _this._index = index;
        _this._fileInfo = currentFileInfo;
        _this.isEvald = isEvald;
        return _this;
    }
    URL.prototype.accept = function (visitor) {
        this.value = visitor.visit(this.value);
    };
    URL.prototype.genCSS = function (context, output) {
        output.add('url(');
        this.value.genCSS(context, output);
        output.add(')');
    };
    URL.prototype.eval = function (context) {
        var val = this.value.eval(context);
        var rootpath;
        if (!this.isEvald) {
            // Add the rootpath if the URL requires a rewrite
            rootpath = this.fileInfo() && this.fileInfo().rootpath;
            if (typeof rootpath === 'string' &&
                typeof val.value === 'string' &&
                context.pathRequiresRewrite(val.value)) {
                if (!val.quote) {
                    rootpath = escapePath(rootpath);
                }
                val.value = context.rewritePath(val.value, rootpath);
            }
            else {
                val.value = context.normalizePath(val.value);
            }
            // Add url args if enabled
            if (context.urlArgs) {
                if (!val.value.match(/^\s*data:/)) {
                    var delimiter = val.value.indexOf('?') === -1 ? '?' : '&';
                    var urlArgs = delimiter + context.urlArgs;
                    if (val.value.indexOf('#') !== -1) {
                        val.value = val.value.replace('#', urlArgs + "#");
                    }
                    else {
                        val.value += urlArgs;
                    }
                }
            }
        }
        return new URL(val, this.getIndex(), this.fileInfo(), true);
    };
    return URL;
}(node_1.default));
URL.prototype.type = 'Url';
function escapePath(path) {
    return path.replace(/[\(\)'"\s]/g, function (match) { return "\\" + match; });
}
exports.default = URL;
//# sourceMappingURL=url.js.map