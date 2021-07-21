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
 * The class to find a pattern in strings as handling escape sequences.
 * It ignores the found pattern if it's escaped with `\`.
 *
 * @see {@link https://eslint-utils.mysticatea.dev/api/ast-utils.html#patternmatcher-class}
 */
const PatternMatcher = eslintUtils.PatternMatcher;
exports.PatternMatcher = PatternMatcher;
//# sourceMappingURL=PatternMatcher.js.map