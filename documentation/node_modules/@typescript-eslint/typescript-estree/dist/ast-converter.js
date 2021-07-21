"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const convert_1 = require("./convert");
const convert_comments_1 = require("./convert-comments");
const node_utils_1 = require("./node-utils");
const simple_traverse_1 = require("./simple-traverse");
function astConverter(ast, extra, shouldPreserveNodeMaps) {
    /**
     * The TypeScript compiler produced fundamental parse errors when parsing the
     * source.
     */
    // internal typescript api...
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const parseDiagnostics = ast.parseDiagnostics;
    if (parseDiagnostics.length) {
        throw convert_1.convertError(parseDiagnostics[0]);
    }
    /**
     * Recursively convert the TypeScript AST into an ESTree-compatible AST
     */
    const instance = new convert_1.Converter(ast, {
        errorOnUnknownASTType: extra.errorOnUnknownASTType || false,
        useJSXTextNode: extra.useJSXTextNode || false,
        shouldPreserveNodeMaps,
    });
    const estree = instance.convertProgram();
    /**
     * Optionally remove range and loc if specified
     */
    if (!extra.range || !extra.loc) {
        simple_traverse_1.simpleTraverse(estree, {
            enter: node => {
                if (!extra.range) {
                    delete node.range;
                }
                if (!extra.loc) {
                    delete node.loc;
                }
            },
        });
    }
    /**
     * Optionally convert and include all tokens in the AST
     */
    if (extra.tokens) {
        estree.tokens = node_utils_1.convertTokens(ast);
    }
    /**
     * Optionally convert and include all comments in the AST
     */
    if (extra.comment) {
        estree.comments = convert_comments_1.convertComments(ast, extra.code);
    }
    const astMaps = shouldPreserveNodeMaps ? instance.getASTMaps() : undefined;
    return { estree, astMaps };
}
exports.astConverter = astConverter;
//# sourceMappingURL=ast-converter.js.map