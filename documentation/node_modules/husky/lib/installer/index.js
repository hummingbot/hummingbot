"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const debug_1 = require("../debug");
const getConf_1 = require("../getConf");
const hooks_1 = require("./hooks");
const localScript_1 = require("./localScript");
const mainScript_1 = require("./mainScript");
// This prevents the case where someone would want to debug a node_module that has
// husky as devDependency and run npm install from node_modules directory
function isInNodeModules(dir) {
    return dir.indexOf('node_modules') !== -1;
}
function getGitHooksDir(gitDir) {
    return path_1.default.join(gitDir, 'hooks');
}
function install({ absoluteGitCommonDir, relativeUserPkgDir, userPkgDir, pmName, // package manager name
isCI, }) {
    // Get conf from package.json or .huskyrc
    const conf = getConf_1.getConf(userPkgDir);
    // Checks
    if (isCI && conf.skipCI) {
        console.log('CI detected, skipping Git hooks installation.');
        return;
    }
    if (isInNodeModules(userPkgDir)) {
        console.log('Trying to install from node_modules directory, skipping Git hooks installation.');
        return;
    }
    // Create hooks directory if it doesn't exist
    const gitHooksDir = getGitHooksDir(absoluteGitCommonDir);
    if (!fs_1.default.existsSync(gitHooksDir)) {
        fs_1.default.mkdirSync(gitHooksDir);
    }
    debug_1.debug(`Installing hooks in ${gitHooksDir}`);
    hooks_1.createHooks(gitHooksDir);
    localScript_1.createLocalScript(gitHooksDir, pmName, relativeUserPkgDir);
    mainScript_1.createMainScript(gitHooksDir);
}
exports.install = install;
function uninstall({ absoluteGitCommonDir, userPkgDir, }) {
    if (isInNodeModules(userPkgDir)) {
        console.log('Trying to uninstall from node_modules directory, skipping Git hooks uninstallation.');
        return;
    }
    // Remove hooks
    const gitHooksDir = getGitHooksDir(absoluteGitCommonDir);
    hooks_1.removeHooks(gitHooksDir);
    localScript_1.removeLocalScript(gitHooksDir);
    mainScript_1.removeMainScript(gitHooksDir);
}
exports.uninstall = uninstall;
