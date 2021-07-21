"use strict";
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (Object.hasOwnProperty.call(mod, k)) result[k] = mod[k];
    result["default"] = mod;
    return result;
};
Object.defineProperty(exports, "__esModule", { value: true });
const ts = __importStar(require("typescript"));
const util_1 = require("tsutils/util/util");
const node_utils_1 = require("./node-utils");
const ts_estree_1 = require("./ts-estree");
/**
 * Convert all comments for the given AST.
 * @param ast the AST object
 * @param code the TypeScript code
 * @returns the converted ESTreeComment
 * @private
 */
function convertComments(ast, code) {
    const comments = [];
    util_1.forEachComment(ast, (_, comment) => {
        const type = comment.kind == ts.SyntaxKind.SingleLineCommentTrivia
            ? ts_estree_1.AST_TOKEN_TYPES.Line
            : ts_estree_1.AST_TOKEN_TYPES.Block;
        const range = [comment.pos, comment.end];
        const loc = node_utils_1.getLocFor(range[0], range[1], ast);
        // both comments start with 2 characters - /* or //
        const textStart = range[0] + 2;
        const textEnd = comment.kind === ts.SyntaxKind.SingleLineCommentTrivia
            ? // single line comments end at the end
                range[1] - textStart
            : // multiline comments end 2 characters early
                range[1] - textStart - 2;
        comments.push({
            type,
            value: code.substr(textStart, textEnd),
            range,
            loc,
        });
    }, ast);
    return comments;
}
exports.convertComments = convertComments;
//# sourceMappingURL=convert-comments.js.map