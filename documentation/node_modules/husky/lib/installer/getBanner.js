"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const path = require("path");
const read_pkg_1 = require("../read-pkg");
function getBanner() {
    const pkgHomepage = process.env.npm_package_homepage;
    const pkgDirectory = process.env.PWD;
    const { homepage: huskyHomepage, version: huskyVersion } = read_pkg_1.readPkg(path.join(__dirname, '../..'));
    const createdAt = new Date().toLocaleString();
    return `# Created by Husky v${huskyVersion} (${huskyHomepage})
#   At: ${createdAt}
#   From: ${pkgDirectory} (${pkgHomepage})`;
}
exports.getBanner = getBanner;
