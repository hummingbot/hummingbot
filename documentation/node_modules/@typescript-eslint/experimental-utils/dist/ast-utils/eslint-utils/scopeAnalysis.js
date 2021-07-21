"use strict";
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (Object.hasOwnProperty.call(mod, k)) result[k] = mod[k];
    result["default"] = mod;
    return result;
};
Object.defineProperty(exports, "__esModule", { value: true });
const eslintUtils = __importStar(require("eslint-utils"));
/**
 * Get the variable of a given name.
 *
 * @see {@link https://eslint-utils.mysticatea.dev/api/scope-utils.html#findvariable}
 */
const findVariable = eslintUtils.findVariable;
exports.findVariable = findVariable;
/**
 * Get the innermost scope which contains a given node.
 *
 * @see {@link https://eslint-utils.mysticatea.dev/api/scope-utils.html#getinnermostscope}
 * @returns The innermost scope which contains the given node.
 * If such scope doesn't exist then it returns the 1st argument `initialScope`.
 */
const getInnermostScope = eslintUtils.getInnermostScope;
exports.getInnermostScope = getInnermostScope;
//# sourceMappingURL=scopeAnalysis.js.map