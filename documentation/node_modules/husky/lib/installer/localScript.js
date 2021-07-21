"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const fs = require("fs");
const path = require("path");
const getBanner_1 = require("./getBanner");
function getLocalScript(pmName, relativeUserPkgDir) {
    return `${getBanner_1.getBanner()}

packageManager=${pmName}
cd "${relativeUserPkgDir}"
`;
}
exports.getLocalScript = getLocalScript;
function createLocalScript(gitHooksDir, pmName, relativeUserPkgDir) {
    fs.writeFileSync(path.join(gitHooksDir, 'husky.local.sh'), getLocalScript(pmName, relativeUserPkgDir), 'utf-8');
}
exports.createLocalScript = createLocalScript;
function removeLocalScript(gitHooksDir) {
    const filename = path.join(gitHooksDir, 'husky.local.sh');
    if (fs.existsSync(filename)) {
        fs.unlinkSync(filename);
    }
}
exports.removeLocalScript = removeLocalScript;
