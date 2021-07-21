"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const cp = require("child_process");
const find_versions_1 = __importDefault(require("find-versions"));
const compare_versions_1 = __importDefault(require("compare-versions"));
function checkGitVersion() {
    const { status, stderr, stdout } = cp.spawnSync('git', ['--version']);
    if (status !== 0) {
        throw new Error(stderr.toString());
    }
    const [version] = find_versions_1.default(stdout.toString());
    if (compare_versions_1.default(version, '2.13.0') === -1) {
        throw new Error(`Husky requires Git >=2.13.0. Got v${version}.`);
    }
}
exports.checkGitVersion = checkGitVersion;
