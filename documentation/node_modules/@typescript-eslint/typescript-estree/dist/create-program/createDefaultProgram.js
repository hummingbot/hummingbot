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
const path_1 = __importDefault(require("path"));
const ts = __importStar(require("typescript"));
const shared_1 = require("./shared");
const log = debug_1.default('typescript-eslint:typescript-estree:createDefaultProgram');
/**
 * @param code The code of the file being linted
 * @param extra The config object
 * @param extra.tsconfigRootDir The root directory for relative tsconfig paths
 * @param extra.projects Provided tsconfig paths
 * @returns If found, returns the source file corresponding to the code and the containing program
 */
function createDefaultProgram(code, extra) {
    log('Getting default program for: %s', extra.filePath || 'unnamed file');
    if (!extra.projects || extra.projects.length !== 1) {
        return undefined;
    }
    const tsconfigPath = shared_1.getTsconfigPath(extra.projects[0], extra);
    const commandLine = ts.getParsedCommandLineOfConfigFile(tsconfigPath, shared_1.createDefaultCompilerOptionsFromExtra(extra), Object.assign(Object.assign({}, ts.sys), { onUnRecoverableConfigFileDiagnostic: () => { } }));
    if (!commandLine) {
        return undefined;
    }
    const compilerHost = ts.createCompilerHost(commandLine.options, 
    /* setParentNodes */ true);
    const oldReadFile = compilerHost.readFile;
    compilerHost.readFile = (fileName) => path_1.default.normalize(fileName) === path_1.default.normalize(extra.filePath)
        ? code
        : oldReadFile(fileName);
    const program = ts.createProgram([extra.filePath], commandLine.options, compilerHost);
    const ast = program.getSourceFile(extra.filePath);
    return ast && { ast, program };
}
exports.createDefaultProgram = createDefaultProgram;
//# sourceMappingURL=createDefaultProgram.js.map