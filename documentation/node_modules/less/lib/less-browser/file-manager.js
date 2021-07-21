"use strict";
/* global window, XMLHttpRequest */
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
var abstract_file_manager_js_1 = __importDefault(require("../less/environment/abstract-file-manager.js"));
var options;
var logger;
var fileCache = {};
// TODOS - move log somewhere. pathDiff and doing something similar in node. use pathDiff in the other browser file for the initial load
var FileManager = /** @class */ (function (_super) {
    __extends(FileManager, _super);
    function FileManager() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    FileManager.prototype.alwaysMakePathsAbsolute = function () {
        return true;
    };
    FileManager.prototype.join = function (basePath, laterPath) {
        if (!basePath) {
            return laterPath;
        }
        return this.extractUrlParts(laterPath, basePath).path;
    };
    FileManager.prototype.doXHR = function (url, type, callback, errback) {
        var xhr = new XMLHttpRequest();
        var async = options.isFileProtocol ? options.fileAsync : true;
        if (typeof xhr.overrideMimeType === 'function') {
            xhr.overrideMimeType('text/css');
        }
        logger.debug("XHR: Getting '" + url + "'");
        xhr.open('GET', url, async);
        xhr.setRequestHeader('Accept', type || 'text/x-less, text/css; q=0.9, */*; q=0.5');
        xhr.send(null);
        function handleResponse(xhr, callback, errback) {
            if (xhr.status >= 200 && xhr.status < 300) {
                callback(xhr.responseText, xhr.getResponseHeader('Last-Modified'));
            }
            else if (typeof errback === 'function') {
                errback(xhr.status, url);
            }
        }
        if (options.isFileProtocol && !options.fileAsync) {
            if (xhr.status === 0 || (xhr.status >= 200 && xhr.status < 300)) {
                callback(xhr.responseText);
            }
            else {
                errback(xhr.status, url);
            }
        }
        else if (async) {
            xhr.onreadystatechange = function () {
                if (xhr.readyState == 4) {
                    handleResponse(xhr, callback, errback);
                }
            };
        }
        else {
            handleResponse(xhr, callback, errback);
        }
    };
    FileManager.prototype.supports = function () {
        return true;
    };
    FileManager.prototype.clearFileCache = function () {
        fileCache = {};
    };
    FileManager.prototype.loadFile = function (filename, currentDirectory, options, environment) {
        // TODO: Add prefix support like less-node?
        // What about multiple paths?
        if (currentDirectory && !this.isPathAbsolute(filename)) {
            filename = currentDirectory + filename;
        }
        filename = options.ext ? this.tryAppendExtension(filename, options.ext) : filename;
        options = options || {};
        // sheet may be set to the stylesheet for the initial load or a collection of properties including
        // some context variables for imports
        var hrefParts = this.extractUrlParts(filename, window.location.href);
        var href = hrefParts.url;
        var self = this;
        return new Promise(function (resolve, reject) {
            if (options.useFileCache && fileCache[href]) {
                try {
                    var lessText = fileCache[href];
                    return resolve({ contents: lessText, filename: href, webInfo: { lastModified: new Date() } });
                }
                catch (e) {
                    return reject({ filename: href, message: "Error loading file " + href + " error was " + e.message });
                }
            }
            self.doXHR(href, options.mime, function doXHRCallback(data, lastModified) {
                // per file cache
                fileCache[href] = data;
                // Use remote copy (re-parse)
                resolve({ contents: data, filename: href, webInfo: { lastModified: lastModified } });
            }, function doXHRError(status, url) {
                reject({ type: 'File', message: "'" + url + "' wasn't found (" + status + ")", href: href });
            });
        });
    };
    return FileManager;
}(abstract_file_manager_js_1.default));
exports.default = (function (opts, log) {
    options = opts;
    logger = log;
    return FileManager;
});
//# sourceMappingURL=file-manager.js.map