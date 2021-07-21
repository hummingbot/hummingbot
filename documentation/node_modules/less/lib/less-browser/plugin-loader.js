"use strict";
// TODO: Add tests for browser @plugin
/* global window */
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
var abstract_plugin_loader_js_1 = __importDefault(require("../less/environment/abstract-plugin-loader.js"));
/**
 * Browser Plugin Loader
 */
var PluginLoader = /** @class */ (function (_super) {
    __extends(PluginLoader, _super);
    function PluginLoader(less) {
        var _this = _super.call(this) || this;
        _this.less = less;
        return _this;
        // Should we shim this.require for browser? Probably not?
    }
    PluginLoader.prototype.loadPlugin = function (filename, basePath, context, environment, fileManager) {
        return new Promise(function (fulfill, reject) {
            fileManager.loadFile(filename, basePath, context, environment)
                .then(fulfill).catch(reject);
        });
    };
    return PluginLoader;
}(abstract_plugin_loader_js_1.default));
exports.default = PluginLoader;
//# sourceMappingURL=plugin-loader.js.map