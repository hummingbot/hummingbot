"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    Object.defineProperty(o, k2, { enumerable: true, get: function() { return m[k]; } });
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (k !== "default" && Object.hasOwnProperty.call(mod, k)) __createBinding(result, mod, k);
    __setModuleDefault(result, mod);
    return result;
};
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var PromiseConstructor;
var contexts_1 = __importDefault(require("./contexts"));
var parser_1 = __importDefault(require("./parser/parser"));
var plugin_manager_1 = __importDefault(require("./plugin-manager"));
var less_error_1 = __importDefault(require("./less-error"));
var utils = __importStar(require("./utils"));
exports.default = (function (environment, ParseTree, ImportManager) {
    var parse = function (input, options, callback) {
        if (typeof options === 'function') {
            callback = options;
            options = utils.copyOptions(this.options, {});
        }
        else {
            options = utils.copyOptions(this.options, options || {});
        }
        if (!callback) {
            var self_1 = this;
            return new Promise(function (resolve, reject) {
                parse.call(self_1, input, options, function (err, output) {
                    if (err) {
                        reject(err);
                    }
                    else {
                        resolve(output);
                    }
                });
            });
        }
        else {
            var context_1;
            var rootFileInfo = void 0;
            var pluginManager_1 = new plugin_manager_1.default(this, !options.reUsePluginManager);
            options.pluginManager = pluginManager_1;
            context_1 = new contexts_1.default.Parse(options);
            if (options.rootFileInfo) {
                rootFileInfo = options.rootFileInfo;
            }
            else {
                var filename = options.filename || 'input';
                var entryPath = filename.replace(/[^\/\\]*$/, '');
                rootFileInfo = {
                    filename: filename,
                    rewriteUrls: context_1.rewriteUrls,
                    rootpath: context_1.rootpath || '',
                    currentDirectory: entryPath,
                    entryPath: entryPath,
                    rootFilename: filename
                };
                // add in a missing trailing slash
                if (rootFileInfo.rootpath && rootFileInfo.rootpath.slice(-1) !== '/') {
                    rootFileInfo.rootpath += '/';
                }
            }
            var imports_1 = new ImportManager(this, context_1, rootFileInfo);
            this.importManager = imports_1;
            // TODO: allow the plugins to be just a list of paths or names
            // Do an async plugin queue like lessc
            if (options.plugins) {
                options.plugins.forEach(function (plugin) {
                    var evalResult;
                    var contents;
                    if (plugin.fileContent) {
                        contents = plugin.fileContent.replace(/^\uFEFF/, '');
                        evalResult = pluginManager_1.Loader.evalPlugin(contents, context_1, imports_1, plugin.options, plugin.filename);
                        if (evalResult instanceof less_error_1.default) {
                            return callback(evalResult);
                        }
                    }
                    else {
                        pluginManager_1.addPlugin(plugin);
                    }
                });
            }
            new parser_1.default(context_1, imports_1, rootFileInfo)
                .parse(input, function (e, root) {
                if (e) {
                    return callback(e);
                }
                callback(null, root, imports_1, options);
            }, options);
        }
    };
    return parse;
});
//# sourceMappingURL=parse.js.map