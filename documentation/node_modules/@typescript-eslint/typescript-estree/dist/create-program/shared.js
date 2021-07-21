"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (Object.hasOwnProperty.call(mod, k)) result[k] = mod[k];
    result["default"] = mod;
    return result;
};
Object.defineProperty(exports, "__esModule", { value: true });
const path_1 = __importDefault(require("path"));
const ts = __importStar(require("typescript"));
/**
 * Default compiler options for program generation from single root file
 */
const DEFAULT_COMPILER_OPTIONS = {
    allowNonTsExtensions: true,
    allowJs: true,
    checkJs: true,
    noEmit: true,
    // extendedDiagnostics: true,
    noUnusedLocals: true,
    noUnusedParameters: true,
};
function createDefaultCompilerOptionsFromExtra(extra) {
    if (extra.debugLevel.has('typescript')) {
        return Object.assign(Object.assign({}, DEFAULT_COMPILER_OPTIONS), { extendedDiagnostics: true });
    }
    return DEFAULT_COMPILER_OPTIONS;
}
exports.createDefaultCompilerOptionsFromExtra = createDefaultCompilerOptionsFromExtra;
// typescript doesn't provide a ts.sys implementation for browser environments
const useCaseSensitiveFileNames = ts.sys !== undefined ? ts.sys.useCaseSensitiveFileNames : true;
const correctPathCasing = useCaseSensitiveFileNames
    ? (filePath) => filePath
    : (filePath) => filePath.toLowerCase();
function getCanonicalFileName(filePath) {
    let normalized = path_1.default.normalize(filePath);
    if (normalized.endsWith(path_1.default.sep)) {
        normalized = normalized.substr(0, normalized.length - 1);
    }
    return correctPathCasing(normalized);
}
exports.getCanonicalFileName = getCanonicalFileName;
function ensureAbsolutePath(p, extra) {
    return path_1.default.isAbsolute(p)
        ? p
        : path_1.default.join(extra.tsconfigRootDir || process.cwd(), p);
}
exports.ensureAbsolutePath = ensureAbsolutePath;
function getTsconfigPath(tsconfigPath, extra) {
    return getCanonicalFileName(ensureAbsolutePath(tsconfigPath, extra));
}
exports.getTsconfigPath = getTsconfigPath;
function canonicalDirname(p) {
    return path_1.default.dirname(p);
}
exports.canonicalDirname = canonicalDirname;
function getScriptKind(extra, filePath = extra.filePath) {
    const extension = path_1.default.extname(filePath).toLowerCase();
    // note - we respect the user's extension when it is known  we could override it and force it to match their
    // jsx setting, but that could create weird situations where we throw parse errors when TSC doesn't
    switch (extension) {
        case '.ts':
            return ts.ScriptKind.TS;
        case '.tsx':
            return ts.ScriptKind.TSX;
        case '.js':
            return ts.ScriptKind.JS;
        case '.jsx':
            return ts.ScriptKind.JSX;
        case '.json':
            return ts.ScriptKind.JSON;
        default:
            // unknown extension, force typescript to ignore the file extension, and respect the user's setting
            return extra.jsx ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
    }
}
exports.getScriptKind = getScriptKind;
//# sourceMappingURL=shared.js.map