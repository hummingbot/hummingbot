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
var Assignment = /** @class */ (function (_super) {
    __extends(Assignment, _super);
    function Assignment(key, val) {
        var _this = _super.call(this) || this;
        _this.key = key;
        _this.value = val;
        return _this;
    }
    Assignment.prototype.accept = function (visitor) {
        this.value = visitor.visit(this.value);
    };
    Assignment.prototype.eval = function (context) {
        if (this.value.eval) {
            return new Assignment(this.key, this.value.eval(context));
        }
        return this;
    };
    Assignment.prototype.genCSS = function (context, output) {
        output.add(this.key + "=");
        if (this.value.genCSS) {
            this.value.genCSS(context, output);
        }
        else {
            output.add(this.value);
        }
    };
    return Assignment;
}(node_1.default));
Assignment.prototype.type = 'Assignment';
exports.default = Assignment;
//# sourceMappingURL=assignment.js.map