"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
//
// index.js
// Should expose the additional browser functions on to the less object
//
var utils_1 = require("./utils");
var less_1 = __importDefault(require("../less"));
var browser_1 = __importDefault(require("./browser"));
var file_manager_1 = __importDefault(require("./file-manager"));
var plugin_loader_1 = __importDefault(require("./plugin-loader"));
var log_listener_1 = __importDefault(require("./log-listener"));
var error_reporting_1 = __importDefault(require("./error-reporting"));
var cache_1 = __importDefault(require("./cache"));
var image_size_1 = __importDefault(require("./image-size"));
exports.default = (function (window, options) {
    var document = window.document;
    var less = less_1.default();
    less.options = options;
    var environment = less.environment;
    var FileManager = file_manager_1.default(options, less.logger);
    var fileManager = new FileManager();
    environment.addFileManager(fileManager);
    less.FileManager = FileManager;
    less.PluginLoader = plugin_loader_1.default;
    log_listener_1.default(less, options);
    var errors = error_reporting_1.default(window, less, options);
    var cache = less.cache = options.cache || cache_1.default(window, options, less.logger);
    image_size_1.default(less.environment);
    // Setup user functions - Deprecate?
    if (options.functions) {
        less.functions.functionRegistry.addMultiple(options.functions);
    }
    var typePattern = /^text\/(x-)?less$/;
    function clone(obj) {
        var cloned = {};
        for (var prop in obj) {
            if (obj.hasOwnProperty(prop)) {
                cloned[prop] = obj[prop];
            }
        }
        return cloned;
    }
    // only really needed for phantom
    function bind(func, thisArg) {
        var curryArgs = Array.prototype.slice.call(arguments, 2);
        return function () {
            var args = curryArgs.concat(Array.prototype.slice.call(arguments, 0));
            return func.apply(thisArg, args);
        };
    }
    function loadStyles(modifyVars) {
        var styles = document.getElementsByTagName('style');
        var style;
        for (var i = 0; i < styles.length; i++) {
            style = styles[i];
            if (style.type.match(typePattern)) {
                var instanceOptions = clone(options);
                instanceOptions.modifyVars = modifyVars;
                var lessText = style.innerHTML || '';
                instanceOptions.filename = document.location.href.replace(/#.*$/, '');
                /* jshint loopfunc:true */
                // use closure to store current style
                less.render(lessText, instanceOptions, bind(function (style, e, result) {
                    if (e) {
                        errors.add(e, 'inline');
                    }
                    else {
                        style.type = 'text/css';
                        if (style.styleSheet) {
                            style.styleSheet.cssText = result.css;
                        }
                        else {
                            style.innerHTML = result.css;
                        }
                    }
                }, null, style));
            }
        }
    }
    function loadStyleSheet(sheet, callback, reload, remaining, modifyVars) {
        var instanceOptions = clone(options);
        utils_1.addDataAttr(instanceOptions, sheet);
        instanceOptions.mime = sheet.type;
        if (modifyVars) {
            instanceOptions.modifyVars = modifyVars;
        }
        function loadInitialFileCallback(loadedFile) {
            var data = loadedFile.contents;
            var path = loadedFile.filename;
            var webInfo = loadedFile.webInfo;
            var newFileInfo = {
                currentDirectory: fileManager.getPath(path),
                filename: path,
                rootFilename: path,
                rewriteUrls: instanceOptions.rewriteUrls
            };
            newFileInfo.entryPath = newFileInfo.currentDirectory;
            newFileInfo.rootpath = instanceOptions.rootpath || newFileInfo.currentDirectory;
            if (webInfo) {
                webInfo.remaining = remaining;
                var css = cache.getCSS(path, webInfo, instanceOptions.modifyVars);
                if (!reload && css) {
                    webInfo.local = true;
                    callback(null, css, data, sheet, webInfo, path);
                    return;
                }
            }
            // TODO add tests around how this behaves when reloading
            errors.remove(path);
            instanceOptions.rootFileInfo = newFileInfo;
            less.render(data, instanceOptions, function (e, result) {
                if (e) {
                    e.href = path;
                    callback(e);
                }
                else {
                    cache.setCSS(sheet.href, webInfo.lastModified, instanceOptions.modifyVars, result.css);
                    callback(null, result.css, data, sheet, webInfo, path);
                }
            });
        }
        fileManager.loadFile(sheet.href, null, instanceOptions, environment)
            .then(function (loadedFile) {
            loadInitialFileCallback(loadedFile);
        }).catch(function (err) {
            console.log(err);
            callback(err);
        });
    }
    function loadStyleSheets(callback, reload, modifyVars) {
        for (var i = 0; i < less.sheets.length; i++) {
            loadStyleSheet(less.sheets[i], callback, reload, less.sheets.length - (i + 1), modifyVars);
        }
    }
    function initRunningMode() {
        if (less.env === 'development') {
            less.watchTimer = setInterval(function () {
                if (less.watchMode) {
                    fileManager.clearFileCache();
                    loadStyleSheets(function (e, css, _, sheet, webInfo) {
                        if (e) {
                            errors.add(e, e.href || sheet.href);
                        }
                        else if (css) {
                            browser_1.default.createCSS(window.document, css, sheet);
                        }
                    });
                }
            }, options.poll);
        }
    }
    //
    // Watch mode
    //
    less.watch = function () {
        if (!less.watchMode) {
            less.env = 'development';
            initRunningMode();
        }
        this.watchMode = true;
        return true;
    };
    less.unwatch = function () { clearInterval(less.watchTimer); this.watchMode = false; return false; };
    //
    // Synchronously get all <link> tags with the 'rel' attribute set to
    // "stylesheet/less".
    //
    less.registerStylesheetsImmediately = function () {
        var links = document.getElementsByTagName('link');
        less.sheets = [];
        for (var i = 0; i < links.length; i++) {
            if (links[i].rel === 'stylesheet/less' || (links[i].rel.match(/stylesheet/) &&
                (links[i].type.match(typePattern)))) {
                less.sheets.push(links[i]);
            }
        }
    };
    //
    // Asynchronously get all <link> tags with the 'rel' attribute set to
    // "stylesheet/less", returning a Promise.
    //
    less.registerStylesheets = function () { return new Promise(function (resolve, reject) {
        less.registerStylesheetsImmediately();
        resolve();
    }); };
    //
    // With this function, it's possible to alter variables and re-render
    // CSS without reloading less-files
    //
    less.modifyVars = function (record) { return less.refresh(true, record, false); };
    less.refresh = function (reload, modifyVars, clearFileCache) {
        if ((reload || clearFileCache) && clearFileCache !== false) {
            fileManager.clearFileCache();
        }
        return new Promise(function (resolve, reject) {
            var startTime;
            var endTime;
            var totalMilliseconds;
            var remainingSheets;
            startTime = endTime = new Date();
            // Set counter for remaining unprocessed sheets
            remainingSheets = less.sheets.length;
            if (remainingSheets === 0) {
                endTime = new Date();
                totalMilliseconds = endTime - startTime;
                less.logger.info('Less has finished and no sheets were loaded.');
                resolve({
                    startTime: startTime,
                    endTime: endTime,
                    totalMilliseconds: totalMilliseconds,
                    sheets: less.sheets.length
                });
            }
            else {
                // Relies on less.sheets array, callback seems to be guaranteed to be called for every element of the array
                loadStyleSheets(function (e, css, _, sheet, webInfo) {
                    if (e) {
                        errors.add(e, e.href || sheet.href);
                        reject(e);
                        return;
                    }
                    if (webInfo.local) {
                        less.logger.info("Loading " + sheet.href + " from cache.");
                    }
                    else {
                        less.logger.info("Rendered " + sheet.href + " successfully.");
                    }
                    browser_1.default.createCSS(window.document, css, sheet);
                    less.logger.info("CSS for " + sheet.href + " generated in " + (new Date() - endTime) + "ms");
                    // Count completed sheet
                    remainingSheets--;
                    // Check if the last remaining sheet was processed and then call the promise
                    if (remainingSheets === 0) {
                        totalMilliseconds = new Date() - startTime;
                        less.logger.info("Less has finished. CSS generated in " + totalMilliseconds + "ms");
                        resolve({
                            startTime: startTime,
                            endTime: endTime,
                            totalMilliseconds: totalMilliseconds,
                            sheets: less.sheets.length
                        });
                    }
                    endTime = new Date();
                }, reload, modifyVars);
            }
            loadStyles(modifyVars);
        });
    };
    less.refreshStyles = loadStyles;
    return less;
});
//# sourceMappingURL=index.js.map