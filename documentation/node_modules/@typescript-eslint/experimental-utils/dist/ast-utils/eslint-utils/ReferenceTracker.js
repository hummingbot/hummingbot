"use strict";
/* eslint-disable @typescript-eslint/no-namespace */
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (Object.hasOwnProperty.call(mod, k)) result[k] = mod[k];
    result["default"] = mod;
    return result;
};
Object.defineProperty(exports, "__esModule", { value: true });
const eslintUtils = __importStar(require("eslint-utils"));
const ReferenceTrackerREAD = eslintUtils.ReferenceTracker.READ;
const ReferenceTrackerCALL = eslintUtils.ReferenceTracker.CALL;
const ReferenceTrackerCONSTRUCT = eslintUtils.ReferenceTracker.CONSTRUCT;
/**
 * The tracker for references. This provides reference tracking for global variables, CommonJS modules, and ES modules.
 *
 * @see {@link https://eslint-utils.mysticatea.dev/api/scope-utils.html#referencetracker-class}
 */
const ReferenceTracker = eslintUtils.ReferenceTracker;
exports.ReferenceTracker = ReferenceTracker;
//# sourceMappingURL=ReferenceTracker.js.map