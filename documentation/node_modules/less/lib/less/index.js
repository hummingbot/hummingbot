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
var __spreadArrays = (this && this.__spreadArrays) || function () {
    for (var s = 0, i = 0, il = arguments.length; i < il; i++) s += arguments[i].length;
    for (var r = Array(s), k = 0, i = 0; i < il; i++)
        for (var a = arguments[i], j = 0, jl = a.length; j < jl; j++, k++)
            r[k] = a[j];
    return r;
};
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var data_1 = __importDefault(require("./data"));
var tree_1 = __importDefault(require("./tree"));
var environment_1 = __importDefault(require("./environment/environment"));
var abstract_file_manager_1 = __importDefault(require("./environment/abstract-file-manager"));
var abstract_plugin_loader_1 = __importDefault(require("./environment/abstract-plugin-loader"));
var visitors_1 = __importDefault(require("./visitors"));
var parser_1 = __importDefault(require("./parser/parser"));
var functions_1 = __importDefault(require("./functions"));
var contexts_1 = __importDefault(require("./contexts"));
var source_map_output_1 = __importDefault(require("./source-map-output"));
var source_map_builder_1 = __importDefault(require("./source-map-builder"));
var parse_tree_1 = __importDefault(require("./parse-tree"));
var import_manager_1 = __importDefault(require("./import-manager"));
var render_1 = __importDefault(require("./render"));
var parse_1 = __importDefault(require("./parse"));
var less_error_1 = __importDefault(require("./less-error"));
var transform_tree_1 = __importDefault(require("./transform-tree"));
var utils = __importStar(require("./utils"));
var plugin_manager_1 = __importDefault(require("./plugin-manager"));
var logger_1 = __importDefault(require("./logger"));
exports.default = (function (environment, fileManagers) {
    /**
     * @todo
     * This original code could be improved quite a bit.
     * Many classes / modules currently add side-effects / mutations to passed in objects,
     * which makes it hard to refactor and reason about.
     */
    environment = new environment_1.default(environment, fileManagers);
    var SourceMapOutput = source_map_output_1.default(environment);
    var SourceMapBuilder = source_map_builder_1.default(SourceMapOutput, environment);
    var ParseTree = parse_tree_1.default(SourceMapBuilder);
    var ImportManager = import_manager_1.default(environment);
    var render = render_1.default(environment, ParseTree, ImportManager);
    var parse = parse_1.default(environment, ParseTree, ImportManager);
    var functions = functions_1.default(environment);
    /**
     * @todo
     * This root properties / methods need to be organized.
     * It's not clear what should / must be public and why.
     */
    var initial = {
        version: [3, 12, 2],
        data: data_1.default,
        tree: tree_1.default,
        Environment: environment_1.default,
        AbstractFileManager: abstract_file_manager_1.default,
        AbstractPluginLoader: abstract_plugin_loader_1.default,
        environment: environment,
        visitors: visitors_1.default,
        Parser: parser_1.default,
        functions: functions,
        contexts: contexts_1.default,
        SourceMapOutput: SourceMapOutput,
        SourceMapBuilder: SourceMapBuilder,
        ParseTree: ParseTree,
        ImportManager: ImportManager,
        render: render,
        parse: parse,
        LessError: less_error_1.default,
        transformTree: transform_tree_1.default,
        utils: utils,
        PluginManager: plugin_manager_1.default,
        logger: logger_1.default
    };
    // Create a public API
    var ctor = function (t) { return function () {
        var args = [];
        for (var _i = 0; _i < arguments.length; _i++) {
            args[_i] = arguments[_i];
        }
        return new (t.bind.apply(t, __spreadArrays([void 0], args)))();
    }; };
    var t;
    var api = Object.create(initial);
    for (var n in initial.tree) {
        /* eslint guard-for-in: 0 */
        t = initial.tree[n];
        if (typeof t === 'function') {
            api[n.toLowerCase()] = ctor(t);
        }
        else {
            api[n] = Object.create(null);
            for (var o in t) {
                /* eslint guard-for-in: 0 */
                api[n][o.toLowerCase()] = ctor(t[o]);
            }
        }
    }
    /**
     * Some of the functions assume a `this` context of the API object,
     * which causes it to fail when wrapped for ES6 imports.
     *
     * An assumed `this` should be removed in the future.
     */
    initial.parse = initial.parse.bind(api);
    initial.render = initial.render.bind(api);
    return api;
});
//# sourceMappingURL=index.js.map