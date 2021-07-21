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
var _noSpaceCombinators = {
    '': true,
    ' ': true,
    '|': true
};
var Combinator = /** @class */ (function (_super) {
    __extends(Combinator, _super);
    function Combinator(value) {
        var _this = _super.call(this) || this;
        if (value === ' ') {
            _this.value = ' ';
            _this.emptyOrWhitespace = true;
        }
        else {
            _this.value = value ? value.trim() : '';
            _this.emptyOrWhitespace = _this.value === '';
        }
        return _this;
    }
    Combinator.prototype.genCSS = function (context, output) {
        var spaceOrEmpty = (context.compress || _noSpaceCombinators[this.value]) ? '' : ' ';
        output.add(spaceOrEmpty + this.value + spaceOrEmpty);
    };
    return Combinator;
}(node_1.default));
Combinator.prototype.type = 'Combinator';
exports.default = Combinator;
//# sourceMappingURL=combinator.js.map