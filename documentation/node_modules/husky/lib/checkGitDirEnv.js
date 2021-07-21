"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const debug_1 = require("./debug");
function checkGitDirEnv() {
    if (process.env.GIT_DIR) {
        debug_1.debug(`GIT_DIR environment variable is set to ${process.env.GIT_DIR}`);
        debug_1.debug(`If you're getting "fatal: not a git repository" errors, check GIT_DIR value`);
    }
}
exports.checkGitDirEnv = checkGitDirEnv;
