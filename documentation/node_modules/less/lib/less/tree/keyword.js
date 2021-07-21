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
var Keyword = /** @class */ (function (_super) {
    __extends(Keyword, _super);
    function Keyword(value) {
        var _this = _super.call(this) || this;
        _this.value = value;
        return _this;
    }
    Keyword.prototype.genCSS = function (context, output) {
        if (this.value === '%') {
            throw { type: 'Syntax', message: 'Invalid % without number' };
        }
        output.add(this.value);
    };
    return Keyword;
}(node_1.default));
Keyword.prototype.type = 'Keyword';
Keyword.True = new Keyword('true');
Keyword.False = new Keyword('false');
exports.default = Keyword;
//# sourceMappingURL=keyword.js.map