"use strict";
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (Object.hasOwnProperty.call(mod, k)) result[k] = mod[k];
    result["default"] = mod;
    return result;
};
Object.defineProperty(exports, "__esModule", { value: true });
const util = __importStar(require("../util"));
exports.default = util.createRule({
    name: 'func-call-spacing',
    meta: {
        type: 'layout',
        docs: {
            description: 'Require or disallow spacing between function identifiers and their invocations',
            category: 'Stylistic Issues',
            recommended: false,
            extendsBaseRule: true,
        },
        fixable: 'whitespace',
        schema: {
            anyOf: [
                {
                    type: 'array',
                    items: [
                        {
                            enum: ['never'],
                        },
                    ],
                    minItems: 0,
                    maxItems: 1,
                },
                {
                    type: 'array',
                    items: [
                        {
                            enum: ['always'],
                        },
                        {
                            type: 'object',
                            properties: {
                                allowNewlines: {
                                    type: 'boolean',
                                },
                            },
                            additionalProperties: false,
                        },
                    ],
                    minItems: 0,
                    maxItems: 2,
                },
            ],
        },
        messages: {
            unexpected: 'Unexpected space or newline between function name and paren.',
            missing: 'Missing space between function name and paren.',
        },
    },
    defaultOptions: ['never', {}],
    create(context, [option, config]) {
        const sourceCode = context.getSourceCode();
        const text = sourceCode.getText();
        /**
         * Check if open space is present in a function name
         * @param {ASTNode} node node to evaluate
         * @returns {void}
         * @private
         */
        function checkSpacing(node) {
            var _a;
            const isOptionalCall = util.isOptionalOptionalCallExpression(node);
            const closingParenToken = sourceCode.getLastToken(node);
            const lastCalleeTokenWithoutPossibleParens = sourceCode.getLastToken((_a = node.typeParameters) !== null && _a !== void 0 ? _a : node.callee);
            const openingParenToken = sourceCode.getFirstTokenBetween(lastCalleeTokenWithoutPossibleParens, closingParenToken, util.isOpeningParenToken);
            if (!openingParenToken || openingParenToken.range[1] >= node.range[1]) {
                // new expression with no parens...
                return;
            }
            const lastCalleeToken = sourceCode.getTokenBefore(openingParenToken, util.isNotOptionalChainPunctuator);
            const textBetweenTokens = text
                .slice(lastCalleeToken.range[1], openingParenToken.range[0])
                .replace(/\/\*.*?\*\//gu, '');
            const hasWhitespace = /\s/u.test(textBetweenTokens);
            const hasNewline = hasWhitespace && util.LINEBREAK_MATCHER.test(textBetweenTokens);
            if (option === 'never') {
                if (hasWhitespace) {
                    return context.report({
                        node,
                        loc: lastCalleeToken.loc.start,
                        messageId: 'unexpected',
                        fix(fixer) {
                            /*
                             * Only autofix if there is no newline
                             * https://github.com/eslint/eslint/issues/7787
                             */
                            if (!hasNewline &&
                                // don't fix optional calls
                                !isOptionalCall) {
                                return fixer.removeRange([
                                    lastCalleeToken.range[1],
                                    openingParenToken.range[0],
                                ]);
                            }
                            return null;
                        },
                    });
                }
            }
            else if (isOptionalCall) {
                // disallow:
                // foo?. ();
                // foo ?.();
                // foo ?. ();
                if (hasWhitespace || hasNewline) {
                    context.report({
                        node,
                        loc: lastCalleeToken.loc.start,
                        messageId: 'unexpected',
                    });
                }
            }
            else {
                if (!hasWhitespace) {
                    context.report({
                        node,
                        loc: lastCalleeToken.loc.start,
                        messageId: 'missing',
                        fix(fixer) {
                            return fixer.insertTextBefore(openingParenToken, ' ');
                        },
                    });
                }
                else if (!config.allowNewlines && hasNewline) {
                    context.report({
                        node,
                        loc: lastCalleeToken.loc.start,
                        messageId: 'unexpected',
                        fix(fixer) {
                            return fixer.replaceTextRange([lastCalleeToken.range[1], openingParenToken.range[0]], ' ');
                        },
                    });
                }
            }
        }
        return {
            CallExpression: checkSpacing,
            OptionalCallExpression: checkSpacing,
            NewExpression: checkSpacing,
        };
    },
});
//# sourceMappingURL=func-call-spacing.js.map