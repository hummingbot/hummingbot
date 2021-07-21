"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const checkGitDirEnv_1 = require("../checkGitDirEnv");
const _1 = __importDefault(require("./"));
async function run() {
    checkGitDirEnv_1.checkGitDirEnv();
    try {
        const status = await _1.default(process.argv);
        process.exit(status);
    }
    catch (err) {
        console.log('Husky > unexpected error', err);
        process.exit(1);
    }
}
run();
