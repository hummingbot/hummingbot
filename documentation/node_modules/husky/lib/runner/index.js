"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const chalk_1 = __importDefault(require("chalk"));
const child_process_1 = require("child_process");
const getConf_1 = require("../getConf");
const read_pkg_1 = require("../read-pkg");
// Husky <1.0.0 (commands were defined in pkg.scripts)
function getOldCommand(cwd, hookName) {
    // In some cases, package.json may not exist
    // For example, when switching to gh-page branch
    let pkg = {};
    try {
        pkg = read_pkg_1.readPkg(cwd);
    }
    catch (err) {
        if (err.code !== 'ENOENT') {
            throw err;
        }
    }
    return pkg && pkg.scripts && pkg.scripts[hookName.replace('-', '')];
}
// Husky >= 1.0.0
function getCommand(cwd, hookName) {
    const config = getConf_1.getConf(cwd);
    return config && config.hooks && config.hooks[hookName];
}
function runCommand(cwd, hookName, cmd, env) {
    console.log(`husky > ${hookName} (node ${process.version})`);
    const { status } = child_process_1.spawnSync('sh', ['-c', cmd], {
        cwd,
        env: Object.assign(Object.assign({}, process.env), env),
        stdio: 'inherit',
    });
    if (status !== 0) {
        const noVerifyMessage = [
            'commit-msg',
            'pre-commit',
            'pre-rebase',
            'pre-push',
        ].includes(hookName)
            ? '(add --no-verify to bypass)'
            : '(cannot be bypassed with --no-verify due to Git specs)';
        console.log(`husky > ${hookName} hook failed ${noVerifyMessage}`);
    }
    // If shell exits with 127 it means that some command was not found.
    // However, if husky has been deleted from node_modules, it'll be a 127 too.
    // To be able to distinguish between both cases, 127 is changed to 1.
    if (status === 127) {
        return 1;
    }
    return status || 0;
}
/**
 * @param {array} argv process.argv
 * @param {string} options.cwd cwd
 * @param {promise} options.getStdinFn - used for mocking only
 */
async function run([, , hookName = '', HUSKY_GIT_PARAMS], { cwd = process.cwd() } = {}) {
    const oldCommand = getOldCommand(cwd, hookName);
    const command = getCommand(cwd, hookName);
    // Add HUSKY_GIT_PARAMS to env
    const env = {};
    if (HUSKY_GIT_PARAMS) {
        env.HUSKY_GIT_PARAMS = HUSKY_GIT_PARAMS;
    }
    if (command) {
        return runCommand(cwd, hookName, command, env);
    }
    if (oldCommand) {
        console.log(chalk_1.default.red(`
Warning: Setting ${hookName} script in package.json > scripts will be deprecated.
Please move it to husky.hooks in package.json or .huskyrc file.

For an automatic update you can also run:
npx --no-install husky-upgrade
yarn husky-upgrade

See https://github.com/typicode/husky for more information.
`));
        return runCommand(cwd, hookName, oldCommand, env);
    }
    return 0;
}
exports.default = run;
