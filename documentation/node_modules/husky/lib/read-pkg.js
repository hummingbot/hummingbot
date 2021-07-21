"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
function readPkg(dir) {
    const pkgFile = path_1.default.resolve(dir, 'package.json');
    const pkgStr = fs_1.default.readFileSync(pkgFile, 'utf-8');
    return JSON.parse(pkgStr);
}
exports.readPkg = readPkg;
