"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const cosmiconfig_1 = require("cosmiconfig");
function getConf(dir) {
    const explorer = cosmiconfig_1.cosmiconfigSync('husky');
    const { config = {} } = explorer.search(dir) || {};
    const defaults = {
        skipCI: true,
    };
    return Object.assign(Object.assign({}, defaults), config);
}
exports.getConf = getConf;
