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
const debug_1 = __importDefault(require("debug"));
const ts = __importStar(require("typescript"));
const shared_1 = require("./shared");
const log = debug_1.default('typescript-eslint:typescript-estree:createSourceFile');
function createSourceFile(code, extra) {
    log('Getting AST without type information in %s mode for: %s', extra.jsx ? 'TSX' : 'TS', extra.filePath);
    return ts.createSourceFile(extra.filePath, code, ts.ScriptTarget.Latest, 
    /* setParentNodes */ true, shared_1.getScriptKind(extra));
}
exports.createSourceFile = createSourceFile;
//# sourceMappingURL=createSourceFile.js.map