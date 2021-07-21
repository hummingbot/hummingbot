"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const chalk_1 = __importDefault(require("chalk"));
const ci_info_1 = require("ci-info");
const path_1 = __importDefault(require("path"));
const pkg_dir_1 = __importDefault(require("pkg-dir"));
const which_pm_runs_1 = __importDefault(require("which-pm-runs"));
const checkGitDirEnv_1 = require("../checkGitDirEnv");
const debug_1 = require("../debug");
const _1 = require("./");
const gitRevParse_1 = require("./gitRevParse");
const checkGitVersion_1 = require("./checkGitVersion");
// Skip install if HUSKY_SKIP_INSTALL is true
function checkSkipInstallEnv() {
    if (['1', 'true'].includes(process.env.HUSKY_SKIP_INSTALL || '')) {
        console.log('HUSKY_SKIP_INSTALL is set to true,', 'skipping Git hooks installation.');
        process.exit(0);
    }
}
function getDirs(cwd) {
    const { prefix, gitCommonDir } = gitRevParse_1.gitRevParse(cwd);
    debug_1.debug('Git rev-parse command returned:');
    debug_1.debug(`  --git-common-dir: ${gitCommonDir}`);
    debug_1.debug(`  --show-prefix: ${prefix}`);
    const absoluteGitCommonDir = path_1.default.resolve(cwd, gitCommonDir);
    // Prefix can be an empty string
    const relativeUserPkgDir = prefix || '.';
    return { relativeUserPkgDir, absoluteGitCommonDir };
}
// Get INIT_CWD env variable
function getInitCwdEnv() {
    const { INIT_CWD } = process.env;
    if (INIT_CWD === undefined) {
        const { name, version } = which_pm_runs_1.default();
        throw new Error(`INIT_CWD is not set, please upgrade your package manager (${name} ${version})`);
    }
    debug_1.debug(`INIT_CWD is set to ${INIT_CWD}`);
    return INIT_CWD;
}
function getUserPkgDir(dir) {
    const userPkgDir = pkg_dir_1.default.sync(dir);
    if (userPkgDir === undefined) {
        throw new Error([
            `Can't find package.json in ${dir} directory or parents`,
            'Please check that your project has a package.json or create one and reinstall husky.',
        ].join('\n'));
    }
    return userPkgDir;
}
function run() {
    const action = process.argv[2];
    try {
        console.log('husky > %s git hooks', action === 'install' ? 'Setting up' : 'Uninstalling');
        debug_1.debug(`Current working directory is ${process.cwd()}`);
        if (action === 'install') {
            checkSkipInstallEnv();
            checkGitVersion_1.checkGitVersion();
        }
        const INIT_CWD = getInitCwdEnv();
        const userPkgDir = getUserPkgDir(INIT_CWD);
        checkGitDirEnv_1.checkGitDirEnv();
        const { absoluteGitCommonDir, relativeUserPkgDir } = getDirs(userPkgDir);
        if (action === 'install') {
            const { name: pmName } = which_pm_runs_1.default();
            debug_1.debug(`Package manager: ${pmName}`);
            _1.install({
                absoluteGitCommonDir,
                relativeUserPkgDir,
                userPkgDir,
                pmName,
                isCI: ci_info_1.isCI,
            });
        }
        else {
            _1.uninstall({ absoluteGitCommonDir, userPkgDir });
        }
        console.log(`husky > Done`);
    }
    catch (err) {
        console.log(chalk_1.default.red(err.message.trim()));
        debug_1.debug(err.stack);
        console.log(chalk_1.default.red(`husky > Failed to ${action}`));
    }
}
run();
