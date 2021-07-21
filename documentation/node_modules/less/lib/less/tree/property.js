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
var declaration_1 = __importDefault(require("./declaration"));
var Property = /** @class */ (function (_super) {
    __extends(Property, _super);
    function Property(name, index, currentFileInfo) {
        var _this = _super.call(this) || this;
        _this.name = name;
        _this._index = index;
        _this._fileInfo = currentFileInfo;
        return _this;
    }
    Property.prototype.eval = function (context) {
        var property;
        var name = this.name;
        // TODO: shorten this reference
        var mergeRules = context.pluginManager.less.visitors.ToCSSVisitor.prototype._mergeRules;
        if (this.evaluating) {
            throw { type: 'Name', message: "Recursive property reference for " + name, filename: this.fileInfo().filename,
                index: this.getIndex() };
        }
        this.evaluating = true;
        property = this.find(context.frames, function (frame) {
            var v;
            var vArr = frame.property(name);
            if (vArr) {
                for (var i = 0; i < vArr.length; i++) {
                    v = vArr[i];
                    vArr[i] = new declaration_1.default(v.name, v.value, v.important, v.merge, v.index, v.currentFileInfo, v.inline, v.variable);
                }
                mergeRules(vArr);
                v = vArr[vArr.length - 1];
                if (v.important) {
                    var importantScope = context.importantScope[context.importantScope.length - 1];
                    importantScope.important = v.important;
                }
                v = v.value.eval(context);
                return v;
            }
        });
        if (property) {
            this.evaluating = false;
            return property;
        }
        else {
            throw { type: 'Name', message: "Property '" + name + "' is undefined", filename: this.currentFileInfo.filename,
                index: this.index };
        }
    };
    Property.prototype.find = function (obj, fun) {
        for (var i = 0, r = void 0; i < obj.length; i++) {
            r = fun.call(obj, obj[i]);
            if (r) {
                return r;
            }
        }
        return null;
    };
    return Property;
}(node_1.default));
Property.prototype.type = 'Property';
exports.default = Property;
//# sourceMappingURL=property.js.map