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
var js_eval_node_1 = __importDefault(require("./js-eval-node"));
var dimension_1 = __importDefault(require("./dimension"));
var quoted_1 = __importDefault(require("./quoted"));
var anonymous_1 = __importDefault(require("./anonymous"));
var JavaScript = /** @class */ (function (_super) {
    __extends(JavaScript, _super);
    function JavaScript(string, escaped, index, currentFileInfo) {
        var _this = _super.call(this) || this;
        _this.escaped = escaped;
        _this.expression = string;
        _this._index = index;
        _this._fileInfo = currentFileInfo;
        return _this;
    }
    JavaScript.prototype.eval = function (context) {
        var result = this.evaluateJavaScript(this.expression, context);
        var type = typeof result;
        if (type === 'number' && !isNaN(result)) {
            return new dimension_1.default(result);
        }
        else if (type === 'string') {
            return new quoted_1.default("\"" + result + "\"", result, this.escaped, this._index);
        }
        else if (Array.isArray(result)) {
            return new anonymous_1.default(result.join(', '));
        }
        else {
            return new anonymous_1.default(result);
        }
    };
    return JavaScript;
}(js_eval_node_1.default));
JavaScript.prototype.type = 'JavaScript';
exports.default = JavaScript;
//# sourceMappingURL=javascript.js.map