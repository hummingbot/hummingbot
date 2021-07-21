"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const fs = require("fs");
const path = require("path");
const is_1 = require("./is");
const getBanner_1 = require("./getBanner");
exports.huskyIdentifier = '# husky';
function getHookScript() {
    return `#!/bin/sh
${exports.huskyIdentifier}

${getBanner_1.getBanner()}

. "$(dirname "$0")/husky.sh"
`;
}
exports.getHookScript = getHookScript;
const hookList = [
    'applypatch-msg',
    'pre-applypatch',
    'post-applypatch',
    'pre-commit',
    'pre-merge-commit',
    'prepare-commit-msg',
    'commit-msg',
    'post-commit',
    'pre-rebase',
    'post-checkout',
    'post-merge',
    'pre-push',
    'post-update',
    'push-to-checkout',
    'pre-auto-gc',
    'post-rewrite',
    'sendemail-validate',
];
function getHooks(gitHooksDir) {
    return hookList.map((hookName) => path.join(gitHooksDir, hookName));
}
function writeHook(filename, script) {
    fs.writeFileSync(filename, script, 'utf-8');
    fs.chmodSync(filename, 0o0755);
}
function createHook(filename) {
    const name = path.basename(filename);
    const hookScript = getHookScript();
    // Check if hook exist
    if (fs.existsSync(filename)) {
        const hook = fs.readFileSync(filename, 'utf-8');
        // Migrate
        if (is_1.isGhooks(hook)) {
            console.log(`migrating existing ghooks script: ${name}`);
            return writeHook(filename, hookScript);
        }
        // Migrate
        if (is_1.isPreCommit(hook)) {
            console.log(`migrating existing pre-commit script: ${name}`);
            return writeHook(filename, hookScript);
        }
        // Update
        if (is_1.isHusky(hook) || is_1.isYorkie(hook)) {
            return writeHook(filename, hookScript);
        }
        // Skip
        console.log(`skipping existing user hook: ${name}`);
        return;
    }
    // Create hook if it doesn't exist
    writeHook(filename, hookScript);
}
function createHooks(gitHooksDir) {
    getHooks(gitHooksDir).forEach(createHook);
}
exports.createHooks = createHooks;
function canRemove(filename) {
    if (fs.existsSync(filename)) {
        const data = fs.readFileSync(filename, 'utf-8');
        return is_1.isHusky(data);
    }
    return false;
}
function removeHook(filename) {
    fs.unlinkSync(filename);
}
function removeHooks(gitHooksDir) {
    getHooks(gitHooksDir).filter(canRemove).forEach(removeHook);
}
exports.removeHooks = removeHooks;
