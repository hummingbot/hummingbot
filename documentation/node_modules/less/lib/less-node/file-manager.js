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
var fs_1 = __importDefault(require("./fs"));
var abstract_file_manager_js_1 = __importDefault(require("../less/environment/abstract-file-manager.js"));
var FileManager = /** @class */ (function (_super) {
    __extends(FileManager, _super);
    function FileManager() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    FileManager.prototype.supports = function () {
        return true;
    };
    FileManager.prototype.supportsSync = function () {
        return true;
    };
    FileManager.prototype.loadFile = function (filename, currentDirectory, options, environment, callback) {
        var fullFilename;
        var isAbsoluteFilename = this.isPathAbsolute(filename);
        var filenamesTried = [];
        var self = this;
        var prefix = filename.slice(0, 1);
        var explicit = prefix === '.' || prefix === '/';
        var result = null;
        var isNodeModule = false;
        var npmPrefix = 'npm://';
        options = options || {};
        var paths = isAbsoluteFilename ? [''] : [currentDirectory];
        if (options.paths) {
            paths.push.apply(paths, options.paths);
        }
        if (!isAbsoluteFilename && paths.indexOf('.') === -1) {
            paths.push('.');
        }
        var prefixes = options.prefixes || [''];
        var fileParts = this.extractUrlParts(filename);
        if (options.syncImport) {
            getFileData(returnData, returnData);
            if (callback) {
                callback(result.error, result);
            }
            else {
                return result;
            }
        }
        else {
            // promise is guaranteed to be asyncronous
            // which helps as it allows the file handle
            // to be closed before it continues with the next file
            return new Promise(getFileData);
        }
        function returnData(data) {
            if (!data.filename) {
                result = { error: data };
            }
            else {
                result = data;
            }
        }
        function getFileData(fulfill, reject) {
            (function tryPathIndex(i) {
                if (i < paths.length) {
                    (function tryPrefix(j) {
                        if (j < prefixes.length) {
                            isNodeModule = false;
                            fullFilename = fileParts.rawPath + prefixes[j] + fileParts.filename;
                            if (paths[i]) {
                                fullFilename = path_1.default.join(paths[i], fullFilename);
                            }
                            if (!explicit && paths[i] === '.') {
                                try {
                                    fullFilename = require.resolve(fullFilename);
                                    isNodeModule = true;
                                }
                                catch (e) {
                                    filenamesTried.push(npmPrefix + fullFilename);
                                    tryWithExtension();
                                }
                            }
                            else {
                                tryWithExtension();
                            }
                            function tryWithExtension() {
                                var extFilename = options.ext ? self.tryAppendExtension(fullFilename, options.ext) : fullFilename;
                                if (extFilename !== fullFilename && !explicit && paths[i] === '.') {
                                    try {
                                        fullFilename = require.resolve(extFilename);
                                        isNodeModule = true;
                                    }
                                    catch (e) {
                                        filenamesTried.push(npmPrefix + extFilename);
                                        fullFilename = extFilename;
                                    }
                                }
                                else {
                                    fullFilename = extFilename;
                                }
                            }
                            var readFileArgs = [fullFilename];
                            if (!options.rawBuffer) {
                                readFileArgs.push('utf-8');
                            }
                            if (options.syncImport) {
                                try {
                                    var data = fs_1.default.readFileSync.apply(this, readFileArgs);
                                    fulfill({ contents: data, filename: fullFilename });
                                }
                                catch (e) {
                                    filenamesTried.push(isNodeModule ? npmPrefix + fullFilename : fullFilename);
                                    return tryPrefix(j + 1);
                                }
                            }
                            else {
                                readFileArgs.push(function (e, data) {
                                    if (e) {
                                        filenamesTried.push(isNodeModule ? npmPrefix + fullFilename : fullFilename);
                                        return tryPrefix(j + 1);
                                    }
                                    fulfill({ contents: data, filename: fullFilename });
                                });
                                fs_1.default.readFile.apply(this, readFileArgs);
                            }
                        }
                        else {
                            tryPathIndex(i + 1);
                        }
                    })(0);
                }
                else {
                    reject({ type: 'File', message: "'" + filename + "' wasn't found. Tried - " + filenamesTried.join(',') });
                }
            }(0));
        }
    };
    FileManager.prototype.loadFileSync = function (filename, currentDirectory, options, environment) {
        options.syncImport = true;
        return this.loadFile(filename, currentDirectory, options, environment);
    };
    return FileManager;
}(abstract_file_manager_js_1.default));
exports.default = FileManager;
//# sourceMappingURL=file-manager.js.map