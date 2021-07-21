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
var isUrlRe = /^(?:https?:)?\/\//i;
var url_1 = __importDefault(require("url"));
var request;
var abstract_file_manager_js_1 = __importDefault(require("../less/environment/abstract-file-manager.js"));
var logger_1 = __importDefault(require("../less/logger"));
var UrlFileManager = /** @class */ (function (_super) {
    __extends(UrlFileManager, _super);
    function UrlFileManager() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    UrlFileManager.prototype.supports = function (filename, currentDirectory, options, environment) {
        return isUrlRe.test(filename) || isUrlRe.test(currentDirectory);
    };
    UrlFileManager.prototype.loadFile = function (filename, currentDirectory, options, environment) {
        return new Promise(function (fulfill, reject) {
            if (request === undefined) {
                try {
                    request = require('native-request');
                }
                catch (e) {
                    request = null;
                }
            }
            if (!request) {
                reject({ type: 'File', message: 'optional dependency \'native-request\' required to import over http(s)\n' });
                return;
            }
            var urlStr = isUrlRe.test(filename) ? filename : url_1.default.resolve(currentDirectory, filename);
            /** native-request currently has a bug */
            var hackUrlStr = urlStr.indexOf('?') === -1 ? urlStr + '?' : urlStr;
            request.get(hackUrlStr, function (error, body, status) {
                if (status === 404) {
                    reject({ type: 'File', message: "resource '" + urlStr + "' was not found\n" });
                    return;
                }
                if (error) {
                    reject({ type: 'File', message: "resource '" + urlStr + "' gave this Error:\n  " + error + "\n" });
                    return;
                }
                if (!body) {
                    logger_1.default.warn("Warning: Empty body (HTTP " + status + ") returned by \"" + urlStr + "\"");
                }
                fulfill({ contents: body, filename: urlStr });
            });
        });
    };
    return UrlFileManager;
}(abstract_file_manager_js_1.default));
exports.default = UrlFileManager;
//# sourceMappingURL=url-file-manager.js.map