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
var path_1 = __importDefault(require("path"));
var abstract_plugin_loader_js_1 = __importDefault(require("../less/environment/abstract-plugin-loader.js"));
/**
 * Node Plugin Loader
 */
var PluginLoader = /** @class */ (function (_super) {
    __extends(PluginLoader, _super);
    function PluginLoader(less) {
        var _this = _super.call(this) || this;
        _this.less = less;
        _this.require = function (prefix) {
            prefix = path_1.default.dirname(prefix);
            return function (id) {
                var str = id.substr(0, 2);
                if (str === '..' || str === './') {
                    return require(path_1.default.join(prefix, id));
                }
                else {
                    return require(id);
                }
            };
        };
        return _this;
    }
    PluginLoader.prototype.loadPlugin = function (filename, basePath, context, environment, fileManager) {
        var prefix = filename.slice(0, 1);
        var explicit = prefix === '.' || prefix === '/' || filename.slice(-3).toLowerCase() === '.js';
        if (!explicit) {
            context.prefixes = ['less-plugin-', ''];
        }
        if (context.syncImport) {
            return fileManager.loadFileSync(filename, basePath, context, environment);
        }
        return new Promise(function (fulfill, reject) {
            fileManager.loadFile(filename, basePath, context, environment).then(function (data) {
                try {
                    fulfill(data);
                }
                catch (e) {
                    console.log(e);
                    reject(e);
                }
            }).catch(function (err) {
                reject(err);
            });
        });
    };
    PluginLoader.prototype.loadPluginSync = function (filename, basePath, context, environment, fileManager) {
        context.syncImport = true;
        return this.loadPlugin(filename, basePath, context, environment, fileManager);
    };
    return PluginLoader;
}(abstract_plugin_loader_js_1.default));
exports.default = PluginLoader;
//# sourceMappingURL=plugin-loader.js.map