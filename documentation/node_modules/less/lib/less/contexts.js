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
Object.defineProperty(exports, "__esModule", { value: true });
var contexts = {};
exports.default = contexts;
var Constants = __importStar(require("./constants"));
var copyFromOriginal = function copyFromOriginal(original, destination, propertiesToCopy) {
    if (!original) {
        return;
    }
    for (var i = 0; i < propertiesToCopy.length; i++) {
        if (original.hasOwnProperty(propertiesToCopy[i])) {
            destination[propertiesToCopy[i]] = original[propertiesToCopy[i]];
        }
    }
};
/*
 parse is used whilst parsing
 */
var parseCopyProperties = [
    // options
    'paths',
    'rewriteUrls',
    'rootpath',
    'strictImports',
    'insecure',
    'dumpLineNumbers',
    'compress',
    'syncImport',
    'chunkInput',
    'mime',
    'useFileCache',
    // context
    'processImports',
    // Used by the import manager to stop multiple import visitors being created.
    'pluginManager' // Used as the plugin manager for the session
];
contexts.Parse = function (options) {
    copyFromOriginal(options, this, parseCopyProperties);
    if (typeof this.paths === 'string') {
        this.paths = [this.paths];
    }
};
var evalCopyProperties = [
    'paths',
    'compress',
    'math',
    'strictUnits',
    'sourceMap',
    'importMultiple',
    'urlArgs',
    'javascriptEnabled',
    'pluginManager',
    'importantScope',
    'rewriteUrls' // option - whether to adjust URL's to be relative
];
function isPathRelative(path) {
    return !/^(?:[a-z-]+:|\/|#)/i.test(path);
}
function isPathLocalRelative(path) {
    return path.charAt(0) === '.';
}
contexts.Eval = /** @class */ (function () {
    function Eval(options, frames) {
        copyFromOriginal(options, this, evalCopyProperties);
        if (typeof this.paths === 'string') {
            this.paths = [this.paths];
        }
        this.frames = frames || [];
        this.importantScope = this.importantScope || [];
        this.inCalc = false;
        this.mathOn = true;
    }
    Eval.prototype.enterCalc = function () {
        if (!this.calcStack) {
            this.calcStack = [];
        }
        this.calcStack.push(true);
        this.inCalc = true;
    };
    Eval.prototype.exitCalc = function () {
        this.calcStack.pop();
        if (!this.calcStack.length) {
            this.inCalc = false;
        }
    };
    Eval.prototype.inParenthesis = function () {
        if (!this.parensStack) {
            this.parensStack = [];
        }
        this.parensStack.push(true);
    };
    ;
    Eval.prototype.outOfParenthesis = function () {
        this.parensStack.pop();
    };
    ;
    Eval.prototype.isMathOn = function (op) {
        if (!this.mathOn) {
            return false;
        }
        if (op === '/' && this.math !== Constants.Math.ALWAYS && (!this.parensStack || !this.parensStack.length)) {
            return false;
        }
        if (this.math > Constants.Math.PARENS_DIVISION) {
            return this.parensStack && this.parensStack.length;
        }
        return true;
    };
    Eval.prototype.pathRequiresRewrite = function (path) {
        var isRelative = this.rewriteUrls === Constants.RewriteUrls.LOCAL ? isPathLocalRelative : isPathRelative;
        return isRelative(path);
    };
    Eval.prototype.rewritePath = function (path, rootpath) {
        var newPath;
        rootpath = rootpath || '';
        newPath = this.normalizePath(rootpath + path);
        // If a path was explicit relative and the rootpath was not an absolute path
        // we must ensure that the new path is also explicit relative.
        if (isPathLocalRelative(path) &&
            isPathRelative(rootpath) &&
            isPathLocalRelative(newPath) === false) {
            newPath = "./" + newPath;
        }
        return newPath;
    };
    Eval.prototype.normalizePath = function (path) {
        var segments = path.split('/').reverse();
        var segment;
        path = [];
        while (segments.length !== 0) {
            segment = segments.pop();
            switch (segment) {
                case '.':
                    break;
                case '..':
                    if ((path.length === 0) || (path[path.length - 1] === '..')) {
                        path.push(segment);
                    }
                    else {
                        path.pop();
                    }
                    break;
                default:
                    path.push(segment);
                    break;
            }
        }
        return path.join('/');
    };
    return Eval;
}());
//# sourceMappingURL=contexts.js.map