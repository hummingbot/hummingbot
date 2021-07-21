"use strict";
function __export(m) {
    for (var p in m) if (!exports.hasOwnProperty(p)) exports[p] = m[p];
}
Object.defineProperty(exports, "__esModule", { value: true });
const experimental_utils_1 = require("@typescript-eslint/experimental-utils");
__export(require("./astUtils"));
__export(require("./createRule"));
__export(require("./isTypeReadonly"));
__export(require("./misc"));
__export(require("./nullThrows"));
__export(require("./types"));
// this is done for convenience - saves migrating all of the old rules
const { applyDefault, deepMerge, isObjectNotArray, getParserServices, } = experimental_utils_1.ESLintUtils;
exports.applyDefault = applyDefault;
exports.deepMerge = deepMerge;
exports.isObjectNotArray = isObjectNotArray;
exports.getParserServices = getParserServices;
//# sourceMappingURL=index.js.map