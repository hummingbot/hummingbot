"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const fs = require("fs");
const path = require("path");
const getBanner_1 = require("./getBanner");
const read_pkg_1 = require("../read-pkg");
function getMainScript() {
    const pkg = read_pkg_1.readPkg(path.join(__dirname, '../..'));
    const mainScript = fs
        .readFileSync(path.join(__dirname, '../../sh/husky.sh'), 'utf-8')
        .replace('huskyVersion="0.0.0"', `huskyVersion="${pkg.version}"`);
    return [getBanner_1.getBanner(), '', mainScript].join('\n');
}
exports.getMainScript = getMainScript;
function createMainScript(gitHooksDir) {
    fs.writeFileSync(path.join(gitHooksDir, 'husky.sh'), getMainScript(), 'utf-8');
}
exports.createMainScript = createMainScript;
function removeMainScript(gitHooksDir) {
    const filename = path.join(gitHooksDir, 'husky.sh');
    if (fs.existsSync(filename)) {
        fs.unlinkSync(filename);
    }
}
exports.removeMainScript = removeMainScript;
