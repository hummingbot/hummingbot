"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = (function (SourceMapOutput, environment) {
    var SourceMapBuilder = /** @class */ (function () {
        function SourceMapBuilder(options) {
            this.options = options;
        }
        SourceMapBuilder.prototype.toCSS = function (rootNode, options, imports) {
            var sourceMapOutput = new SourceMapOutput({
                contentsIgnoredCharsMap: imports.contentsIgnoredChars,
                rootNode: rootNode,
                contentsMap: imports.contents,
                sourceMapFilename: this.options.sourceMapFilename,
                sourceMapURL: this.options.sourceMapURL,
                outputFilename: this.options.sourceMapOutputFilename,
                sourceMapBasepath: this.options.sourceMapBasepath,
                sourceMapRootpath: this.options.sourceMapRootpath,
                outputSourceFiles: this.options.outputSourceFiles,
                sourceMapGenerator: this.options.sourceMapGenerator,
                sourceMapFileInline: this.options.sourceMapFileInline,
                disableSourcemapAnnotation: this.options.disableSourcemapAnnotation
            });
            var css = sourceMapOutput.toCSS(options);
            this.sourceMap = sourceMapOutput.sourceMap;
            this.sourceMapURL = sourceMapOutput.sourceMapURL;
            if (this.options.sourceMapInputFilename) {
                this.sourceMapInputFilename = sourceMapOutput.normalizeFilename(this.options.sourceMapInputFilename);
            }
            if (this.options.sourceMapBasepath !== undefined && this.sourceMapURL !== undefined) {
                this.sourceMapURL = sourceMapOutput.removeBasepath(this.sourceMapURL);
            }
            return css + this.getCSSAppendage();
        };
        SourceMapBuilder.prototype.getCSSAppendage = function () {
            var sourceMapURL = this.sourceMapURL;
            if (this.options.sourceMapFileInline) {
                if (this.sourceMap === undefined) {
                    return '';
                }
                sourceMapURL = "data:application/json;base64," + environment.encodeBase64(this.sourceMap);
            }
            if (this.options.disableSourcemapAnnotation) {
                return '';
            }
            if (sourceMapURL) {
                return "/*# sourceMappingURL=" + sourceMapURL + " */";
            }
            return '';
        };
        SourceMapBuilder.prototype.getExternalSourceMap = function () {
            return this.sourceMap;
        };
        SourceMapBuilder.prototype.setExternalSourceMap = function (sourceMap) {
            this.sourceMap = sourceMap;
        };
        SourceMapBuilder.prototype.isInline = function () {
            return this.options.sourceMapFileInline;
        };
        SourceMapBuilder.prototype.getSourceMapURL = function () {
            return this.sourceMapURL;
        };
        SourceMapBuilder.prototype.getOutputFilename = function () {
            return this.options.sourceMapOutputFilename;
        };
        SourceMapBuilder.prototype.getInputFilename = function () {
            return this.sourceMapInputFilename;
        };
        return SourceMapBuilder;
    }());
    return SourceMapBuilder;
});
//# sourceMappingURL=source-map-builder.js.map