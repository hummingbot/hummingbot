"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var less_error_1 = __importDefault(require("./less-error"));
var transform_tree_1 = __importDefault(require("./transform-tree"));
var logger_1 = __importDefault(require("./logger"));
exports.default = (function (SourceMapBuilder) {
    var ParseTree = /** @class */ (function () {
        function ParseTree(root, imports) {
            this.root = root;
            this.imports = imports;
        }
        ParseTree.prototype.toCSS = function (options) {
            var evaldRoot;
            var result = {};
            var sourceMapBuilder;
            try {
                evaldRoot = transform_tree_1.default(this.root, options);
            }
            catch (e) {
                throw new less_error_1.default(e, this.imports);
            }
            try {
                var compress = Boolean(options.compress);
                if (compress) {
                    logger_1.default.warn('The compress option has been deprecated. ' +
                        'We recommend you use a dedicated css minifier, for instance see less-plugin-clean-css.');
                }
                var toCSSOptions = {
                    compress: compress,
                    dumpLineNumbers: options.dumpLineNumbers,
                    strictUnits: Boolean(options.strictUnits),
                    numPrecision: 8
                };
                if (options.sourceMap) {
                    sourceMapBuilder = new SourceMapBuilder(options.sourceMap);
                    result.css = sourceMapBuilder.toCSS(evaldRoot, toCSSOptions, this.imports);
                }
                else {
                    result.css = evaldRoot.toCSS(toCSSOptions);
                }
            }
            catch (e) {
                throw new less_error_1.default(e, this.imports);
            }
            if (options.pluginManager) {
                var postProcessors = options.pluginManager.getPostProcessors();
                for (var i = 0; i < postProcessors.length; i++) {
                    result.css = postProcessors[i].process(result.css, { sourceMap: sourceMapBuilder, options: options, imports: this.imports });
                }
            }
            if (options.sourceMap) {
                result.map = sourceMapBuilder.getExternalSourceMap();
            }
            var rootFilename = this.imports.rootFilename;
            result.imports = this.imports.files.filter(function (file) { return file !== rootFilename; });
            return result;
        };
        return ParseTree;
    }());
    return ParseTree;
});
//# sourceMappingURL=parse-tree.js.map