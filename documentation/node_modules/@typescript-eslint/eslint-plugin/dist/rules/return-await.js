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
const tsutils = __importStar(require("tsutils"));
const ts = __importStar(require("typescript"));
const util = __importStar(require("../util"));
exports.default = util.createRule({
    name: 'return-await',
    meta: {
        docs: {
            description: 'Enforces consistent returning of awaited values',
            category: 'Best Practices',
            recommended: false,
            requiresTypeChecking: true,
            extendsBaseRule: 'no-return-await',
        },
        fixable: 'code',
        type: 'problem',
        messages: {
            nonPromiseAwait: 'Returning an awaited value that is not a promise is not allowed.',
            disallowedPromiseAwait: 'Returning an awaited promise is not allowed in this context.',
            requiredPromiseAwait: 'Returning an awaited promise is required in this context.',
        },
        schema: [
            {
                enum: ['in-try-catch', 'always', 'never'],
            },
        ],
    },
    defaultOptions: ['in-try-catch'],
    create(context, [option]) {
        const parserServices = util.getParserServices(context);
        const checker = parserServices.program.getTypeChecker();
        const sourceCode = context.getSourceCode();
        let scopeInfo = null;
        function enterFunction(node) {
            scopeInfo = {
                hasAsync: node.async,
            };
        }
        function inTryCatch(node) {
            let ancestor = node.parent;
            while (ancestor && !ts.isFunctionLike(ancestor)) {
                if (tsutils.isTryStatement(ancestor) ||
                    tsutils.isCatchClause(ancestor)) {
                    return true;
                }
                ancestor = ancestor.parent;
            }
            return false;
        }
        // function findTokensToRemove()
        function removeAwait(fixer, node) {
            const awaitNode = node.type === experimental_utils_1.AST_NODE_TYPES.ReturnStatement
                ? node.argument
                : node.body;
            // Should always be an await node; but let's be safe.
            /* istanbul ignore if */ if (!util.isAwaitExpression(awaitNode)) {
                return null;
            }
            const awaitToken = sourceCode.getFirstToken(awaitNode, util.isAwaitKeyword);
            // Should always be the case; but let's be safe.
            /* istanbul ignore if */ if (!awaitToken) {
                return null;
            }
            const startAt = awaitToken.range[0];
            let endAt = awaitToken.range[1];
            // Also remove any extraneous whitespace after `await`, if there is any.
            const nextToken = sourceCode.getTokenAfter(awaitToken, {
                includeComments: true,
            });
            if (nextToken) {
                endAt = nextToken.range[0];
            }
            return fixer.removeRange([startAt, endAt]);
        }
        function insertAwait(fixer, node) {
            const targetNode = node.type === experimental_utils_1.AST_NODE_TYPES.ReturnStatement
                ? node.argument
                : node.body;
            // There should always be a target node; but let's be safe.
            /* istanbul ignore if */ if (!targetNode) {
                return null;
            }
            return fixer.insertTextBefore(targetNode, 'await ');
        }
        function test(node, expression) {
            let child;
            const isAwait = tsutils.isAwaitExpression(expression);
            if (isAwait) {
                child = expression.getChildAt(1);
            }
            else {
                child = expression;
            }
            const type = checker.getTypeAtLocation(child);
            const isThenable = tsutils.isThenableType(checker, expression, type);
            if (!isAwait && !isThenable) {
                return;
            }
            if (isAwait && !isThenable) {
                context.report({
                    messageId: 'nonPromiseAwait',
                    node,
                    fix: fixer => removeAwait(fixer, node),
                });
                return;
            }
            if (option === 'always') {
                if (!isAwait && isThenable) {
                    context.report({
                        messageId: 'requiredPromiseAwait',
                        node,
                        fix: fixer => insertAwait(fixer, node),
                    });
                }
                return;
            }
            if (option === 'never') {
                if (isAwait) {
                    context.report({
                        messageId: 'disallowedPromiseAwait',
                        node,
                        fix: fixer => removeAwait(fixer, node),
                    });
                }
                return;
            }
            if (option === 'in-try-catch') {
                const isInTryCatch = inTryCatch(expression);
                if (isAwait && !isInTryCatch) {
                    context.report({
                        messageId: 'disallowedPromiseAwait',
                        node,
                        fix: fixer => removeAwait(fixer, node),
                    });
                }
                else if (!isAwait && isInTryCatch) {
                    context.report({
                        messageId: 'requiredPromiseAwait',
                        node,
                        fix: fixer => insertAwait(fixer, node),
                    });
                }
                return;
            }
        }
        return {
            FunctionDeclaration: enterFunction,
            FunctionExpression: enterFunction,
            ArrowFunctionExpression: enterFunction,
            'ArrowFunctionExpression[async = true]:exit'(node) {
                if (node.body.type !== experimental_utils_1.AST_NODE_TYPES.BlockStatement) {
                    const expression = parserServices.esTreeNodeToTSNodeMap.get(node.body);
                    test(node, expression);
                }
            },
            ReturnStatement(node) {
                if (!scopeInfo || !scopeInfo.hasAsync) {
                    return;
                }
                const originalNode = parserServices.esTreeNodeToTSNodeMap.get(node);
                const { expression } = originalNode;
                if (!expression) {
                    return;
                }
                test(node, expression);
            },
        };
    },
});
//# sourceMappingURL=return-await.js.map