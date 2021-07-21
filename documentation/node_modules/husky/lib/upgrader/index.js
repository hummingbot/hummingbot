"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const read_pkg_1 = require("../read-pkg");
const hookList = {
    applypatchmsg: 'applypatch-msg',
    commitmsg: 'commit-msg',
    postapplypatch: 'post-applypatch',
    postcheckout: 'post-checkout',
    postcommit: 'post-commit',
    postmerge: 'post-merge',
    postreceive: 'post-receive',
    postrewrite: 'post-rewrite',
    postupdate: 'post-update',
    preapplypatch: 'pre-applypatch',
    preautogc: 'pre-auto-gc',
    precommit: 'pre-commit',
    premergecommit: 'pre-merge-commit',
    preparecommitmsg: 'prepare-commit-msg',
    prepush: 'pre-push',
    prerebase: 'pre-rebase',
    prereceive: 'pre-receive',
    pushtocheckout: 'push-to-checkout',
    sendemailvalidate: 'sendemail-validate',
    update: 'update',
};
function upgrade(cwd) {
    const pkgFile = path_1.default.join(cwd, 'package.json');
    if (fs_1.default.existsSync(pkgFile)) {
        const pkg = read_pkg_1.readPkg(cwd);
        console.log(`husky > upgrading ${pkgFile}`);
        // Don't overwrite 'husky' field if it exists
        if (pkg.husky) {
            return console.log(`husky field in package.json isn't empty, skipping automatic upgrade`);
        }
        const hooks = {};
        // Find hooks in package.json 'scripts' field
        Object.keys(hookList).forEach((name) => {
            if (pkg.scripts) {
                const script = pkg.scripts[name];
                if (script) {
                    delete pkg.scripts[name];
                    const newName = hookList[name];
                    hooks[newName] = script.replace(/\bGIT_PARAMS\b/g, 'HUSKY_GIT_PARAMS');
                    console.log(`moved scripts.${name} to husky.hooks.${newName}`);
                }
            }
        });
        // Move found hooks to 'husky.hooks' field
        if (Object.keys(hooks).length) {
            pkg.husky = { hooks };
        }
        else {
            console.log('no hooks found');
        }
        // Update package.json
        fs_1.default.writeFileSync(pkgFile, `${JSON.stringify(pkg, null, 2)}\n`, 'utf-8');
        console.log(`husky > done`);
    }
}
exports.default = upgrade;
