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
    name: 'prefer-nullish-coalescing',
    meta: {
        type: 'suggestion',
        docs: {
            description: 'Enforce the usage of the nullish coalescing operator instead of logical chaining',
            category: 'Best Practices',
            recommended: false,
            suggestion: true,
            requiresTypeChecking: true,
        },
        fixable: 'code',
        messages: {
            preferNullish: 'Prefer using nullish coalescing operator (`??`) instead of a logical or (`||`), as it is a safer operator.',
        },
        schema: [
            {
                type: 'object',
                properties: {
                    ignoreConditionalTests: {
                        type: 'boolean',
                    },
                    ignoreMixedLogicalExpressions: {
                        type: 'boolean',
                    },
                    forceSuggestionFixer: {
                        type: 'boolean',
                    },
                },
                additionalProperties: false,
            },
        ],
    },
    defaultOptions: [
        {
            ignoreConditionalTests: true,
            ignoreMixedLogicalExpressions: true,
            forceSuggestionFixer: false,
        },
    ],
    create(context, [{ ignoreConditionalTests, ignoreMixedLogicalExpressions, forceSuggestionFixer, },]) {
        const parserServices = util.getParserServices(context);
        const sourceCode = context.getSourceCode();
        const checker = parserServices.program.getTypeChecker();
        return {
            'LogicalExpression[operator = "||"]'(node) {
                const tsNode = parserServices.esTreeNodeToTSNodeMap.get(node);
                const type = checker.getTypeAtLocation(tsNode.left);
                const isNullish = util.isNullableType(type, { allowUndefined: true });
                if (!isNullish) {
                    return;
                }
                if (ignoreConditionalTests === true && isConditionalTest(node)) {
                    return;
                }
                const isMixedLogical = isMixedLogicalExpression(node);
                if (ignoreMixedLogicalExpressions === true && isMixedLogical) {
                    return;
                }
                const barBarOperator = util.nullThrows(sourceCode.getTokenAfter(node.left, token => token.type === experimental_utils_1.AST_TOKEN_TYPES.Punctuator &&
                    token.value === node.operator), util.NullThrowsReasons.MissingToken('operator', node.type));
                function* fix(fixer) {
                    if (node.parent && util.isLogicalOrOperator(node.parent)) {
                        // '&&' and '??' operations cannot be mixed without parentheses (e.g. a && b ?? c)
                        if (node.left.type === experimental_utils_1.AST_NODE_TYPES.LogicalExpression &&
                            !util.isLogicalOrOperator(node.left.left)) {
                            yield fixer.insertTextBefore(node.left.right, '(');
                        }
                        else {
                            yield fixer.insertTextBefore(node.left, '(');
                        }
                        yield fixer.insertTextAfter(node.right, ')');
                    }
                    yield fixer.replaceText(barBarOperator, '??');
                }
                const fixer = isMixedLogical || forceSuggestionFixer
                    ? // suggestion instead for cases where we aren't sure if the fixer is completely safe
                        {
                            suggest: [
                                {
                                    messageId: 'preferNullish',
                                    fix,
                                },
                            ],
                        }
                    : { fix };
                context.report(Object.assign({ node: barBarOperator, messageId: 'preferNullish' }, fixer));
            },
        };
    },
});
function isConditionalTest(node) {
    const parents = new Set([node]);
    let current = node.parent;
    while (current) {
        parents.add(current);
        if ((current.type === experimental_utils_1.AST_NODE_TYPES.ConditionalExpression ||
            current.type === experimental_utils_1.AST_NODE_TYPES.DoWhileStatement ||
            current.type === experimental_utils_1.AST_NODE_TYPES.IfStatement ||
            current.type === experimental_utils_1.AST_NODE_TYPES.ForStatement ||
            current.type === experimental_utils_1.AST_NODE_TYPES.WhileStatement) &&
            parents.has(current.test)) {
            return true;
        }
        if ([
            experimental_utils_1.AST_NODE_TYPES.ArrowFunctionExpression,
            experimental_utils_1.AST_NODE_TYPES.FunctionExpression,
        ].includes(current.type)) {
            /**
             * This is a weird situation like:
             * `if (() => a || b) {}`
             * `if (function () { return a || b }) {}`
             */
            return false;
        }
        current = current.parent;
    }
    return false;
}
function isMixedLogicalExpression(node) {
    const seen = new Set();
    const queue = [node.parent, node.left, node.right];
    for (const current of queue) {
        if (seen.has(current)) {
            continue;
        }
        seen.add(current);
        if (current && current.type === experimental_utils_1.AST_NODE_TYPES.LogicalExpression) {
            if (current.operator === '&&') {
                return true;
            }
            else if (current.operator === '||') {
                // check the pieces of the node to catch cases like `a || b || c && d`
                queue.push(current.parent, current.left, current.right);
            }
        }
    }
    return false;
}
//# sourceMappingURL=prefer-nullish-coalescing.js.map