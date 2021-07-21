"use strict";
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (Object.hasOwnProperty.call(mod, k)) result[k] = mod[k];
    result["default"] = mod;
    return result;
};
Object.defineProperty(exports, "__esModule", { value: true });
const experimental_utils_1 = require("@typescript-eslint/experimental-utils");
const util = __importStar(require("../util"));
exports.default = util.createRule({
    name: 'no-non-null-assertion',
    meta: {
        type: 'problem',
        docs: {
            description: 'Disallows non-null assertions using the `!` postfix operator',
            category: 'Stylistic Issues',
            recommended: 'warn',
            suggestion: true,
        },
        messages: {
            noNonNull: 'Forbidden non-null assertion.',
            suggestOptionalChain: 'Consider using the optional chain operator `?.` instead. This operator includes runtime checks, so it is safer than the compile-only non-null assertion operator.',
        },
        schema: [],
    },
    defaultOptions: [],
    create(context) {
        const sourceCode = context.getSourceCode();
        return {
            TSNonNullExpression(node) {
                const suggest = [];
                function convertTokenToOptional(replacement) {
                    return (fixer) => {
                        const operator = sourceCode.getTokenAfter(node.expression, util.isNonNullAssertionPunctuator);
                        if (operator) {
                            return fixer.replaceText(operator, replacement);
                        }
                        return null;
                    };
                }
                function removeToken() {
                    return (fixer) => {
                        const operator = sourceCode.getTokenAfter(node.expression, util.isNonNullAssertionPunctuator);
                        if (operator) {
                            return fixer.remove(operator);
                        }
                        return null;
                    };
                }
                if (node.parent) {
                    if ((node.parent.type === experimental_utils_1.AST_NODE_TYPES.MemberExpression ||
                        node.parent.type === experimental_utils_1.AST_NODE_TYPES.OptionalMemberExpression) &&
                        node.parent.object === node) {
                        if (!node.parent.optional) {
                            if (node.parent.computed) {
                                // it is x![y]?.z
                                suggest.push({
                                    messageId: 'suggestOptionalChain',
                                    fix: convertTokenToOptional('?.'),
                                });
                            }
                            else {
                                // it is x!.y?.z
                                suggest.push({
                                    messageId: 'suggestOptionalChain',
                                    fix: convertTokenToOptional('?'),
                                });
                            }
                        }
                        else {
                            if (node.parent.computed) {
                                // it is x!?.[y].z
                                suggest.push({
                                    messageId: 'suggestOptionalChain',
                                    fix: removeToken(),
                                });
                            }
                            else {
                                // it is x!?.y.z
                                suggest.push({
                                    messageId: 'suggestOptionalChain',
                                    fix: removeToken(),
                                });
                            }
                        }
                    }
                    else if ((node.parent.type === experimental_utils_1.AST_NODE_TYPES.CallExpression ||
                        node.parent.type === experimental_utils_1.AST_NODE_TYPES.OptionalCallExpression) &&
                        node.parent.callee === node) {
                        if (!node.parent.optional) {
                            // it is x.y?.z!()
                            suggest.push({
                                messageId: 'suggestOptionalChain',
                                fix: convertTokenToOptional('?.'),
                            });
                        }
                        else {
                            // it is x.y.z!?.()
                            suggest.push({
                                messageId: 'suggestOptionalChain',
                                fix: removeToken(),
                            });
                        }
                    }
                }
                context.report({
                    node,
                    messageId: 'noNonNull',
                    suggest,
                });
            },
        };
    },
});
//# sourceMappingURL=no-non-null-assertion.js.map