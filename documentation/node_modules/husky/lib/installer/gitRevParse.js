"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const child_process_1 = __importDefault(require("child_process"));
const slash_1 = __importDefault(require("slash"));
function gitRevParse(cwd = process.cwd()) {
    // https://github.com/typicode/husky/issues/580
    // https://github.com/typicode/husky/issues/587
    const { status, stderr, stdout } = child_process_1.default.spawnSync('git', ['rev-parse', '--show-prefix', '--git-common-dir'], { cwd });
    if (status !== 0) {
        throw new Error(stderr.toString());
    }
    const [prefix, gitCommonDir] = stdout
        .toString()
        .split('\n')
        .map((s) => s.trim())
        // Normalize for Windows
        .map(slash_1.default);
    return { prefix, gitCommonDir };
}
exports.gitRevParse = gitRevParse;
