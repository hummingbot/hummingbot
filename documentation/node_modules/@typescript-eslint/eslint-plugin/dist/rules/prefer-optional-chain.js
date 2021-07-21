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
    name: 'prefer-optional-chain',
    meta: {
        type: 'suggestion',
        docs: {
            description: 'Prefer using concise optional chain expressions instead of chained logical ands',
            category: 'Best Practices',
            recommended: false,
            suggestion: true,
        },
        fixable: 'code',
        messages: {
            preferOptionalChain: "Prefer using an optional chain expression instead, as it's more concise and easier to read.",
            optionalChainSuggest: 'Change to an optional chain.',
        },
        schema: [
            {
                type: 'object',
                properties: {
                    suggestInsteadOfAutofix: {
                        type: 'boolean',
                    },
                },
                additionalProperties: false,
            },
        ],
    },
    defaultOptions: [
        {
            suggestInsteadOfAutofix: false,
        },
    ],
    create(context, [options]) {
        const sourceCode = context.getSourceCode();
        return {
            [[
                'LogicalExpression[operator="&&"] > Identifier',
                'LogicalExpression[operator="&&"] > BinaryExpression[operator="!=="]',
                'LogicalExpression[operator="&&"] > BinaryExpression[operator="!="]',
            ].join(',')](initialIdentifierOrNotEqualsExpr) {
                // selector guarantees this cast
                const initialExpression = initialIdentifierOrNotEqualsExpr.parent;
                if (initialExpression.left !== initialIdentifierOrNotEqualsExpr) {
                    // the identifier is not the deepest left node
                    return;
                }
                if (!isValidChainTarget(initialIdentifierOrNotEqualsExpr, true)) {
                    return;
                }
                // walk up the tree to figure out how many logical expressions we can include
                let previous = initialExpression;
                let current = initialExpression;
                let previousLeftText = getText(initialIdentifierOrNotEqualsExpr);
                let optionallyChainedCode = previousLeftText;
                let expressionCount = 1;
                while (current.type === experimental_utils_1.AST_NODE_TYPES.LogicalExpression) {
                    if (!isValidChainTarget(current.right, 
                    // only allow identifiers for the first chain - foo && foo()
                    expressionCount === 1)) {
                        break;
                    }
                    const leftText = previousLeftText;
                    const rightText = getText(current.right);
                    // can't just use startsWith because of cases like foo && fooBar.baz;
                    const matchRegex = new RegExp(`^${
                    // escape regex characters
                    leftText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}[^a-zA-Z0-9_$]`);
                    if (!matchRegex.test(rightText) &&
                        // handle redundant cases like foo.bar && foo.bar
                        leftText !== rightText) {
                        break;
                    }
                    // omit weird doubled up expression that make no sense like foo.bar && foo.bar
                    if (rightText !== leftText) {
                        expressionCount += 1;
                        previousLeftText = rightText;
                        /*
                        Diff the left and right text to construct the fix string
                        There are the following cases:
            
                        1)
                        rightText === 'foo.bar.baz.buzz'
                        leftText === 'foo.bar.baz'
                        diff === '.buzz'
            
                        2)
                        rightText === 'foo.bar.baz.buzz()'
                        leftText === 'foo.bar.baz'
                        diff === '.buzz()'
            
                        3)
                        rightText === 'foo.bar.baz.buzz()'
                        leftText === 'foo.bar.baz.buzz'
                        diff === '()'
            
                        4)
                        rightText === 'foo.bar.baz[buzz]'
                        leftText === 'foo.bar.baz'
                        diff === '[buzz]'
            
                        5)
                        rightText === 'foo.bar.baz?.buzz'
                        leftText === 'foo.bar.baz'
                        diff === '?.buzz'
                        */
                        const diff = rightText.replace(leftText, '');
                        if (diff.startsWith('?')) {
                            // item was "pre optional chained"
                            optionallyChainedCode += diff;
                        }
                        else {
                            const needsDot = diff.startsWith('(') || diff.startsWith('[');
                            optionallyChainedCode += `?${needsDot ? '.' : ''}${diff}`;
                        }
                    }
                    previous = current;
                    current = util.nullThrows(current.parent, util.NullThrowsReasons.MissingParent);
                }
                if (expressionCount > 1) {
                    if (previous.right.type === experimental_utils_1.AST_NODE_TYPES.BinaryExpression) {
                        // case like foo && foo.bar !== someValue
                        optionallyChainedCode += ` ${previous.right.operator} ${sourceCode.getText(previous.right.right)}`;
                    }
                    if (!options.suggestInsteadOfAutofix) {
                        context.report({
                            node: previous,
                            messageId: 'preferOptionalChain',
                            fix(fixer) {
                                return fixer.replaceText(previous, optionallyChainedCode);
                            },
                        });
                    }
                    else {
                        context.report({
                            node: previous,
                            messageId: 'preferOptionalChain',
                            suggest: [
                                {
                                    messageId: 'optionalChainSuggest',
                                    fix: (fixer) => [
                                        fixer.replaceText(previous, optionallyChainedCode),
                                    ],
                                },
                            ],
                        });
                    }
                }
            },
        };
        function getText(node) {
            if (node.type === experimental_utils_1.AST_NODE_TYPES.BinaryExpression) {
                return getText(
                // isValidChainTarget ensures this is type safe
                node.left);
            }
            if (node.type === experimental_utils_1.AST_NODE_TYPES.CallExpression ||
                node.type === experimental_utils_1.AST_NODE_TYPES.OptionalCallExpression) {
                const calleeText = getText(
                // isValidChainTarget ensures this is type safe
                node.callee);
                // ensure that the call arguments are left untouched, or else we can break cases that _need_ whitespace:
                // - JSX: <Foo Needs Space Between Attrs />
                // - Unary Operators: typeof foo, await bar, delete baz
                const closingParenToken = util.nullThrows(sourceCode.getLastToken(node), util.NullThrowsReasons.MissingToken('closing parenthesis', node.type));
                const openingParenToken = util.nullThrows(sourceCode.getFirstTokenBetween(node.callee, closingParenToken, util.isOpeningParenToken), util.NullThrowsReasons.MissingToken('opening parenthesis', node.type));
                const argumentsText = sourceCode.text.substring(openingParenToken.range[0], closingParenToken.range[1]);
                return `${calleeText}${argumentsText}`;
            }
            if (node.type === experimental_utils_1.AST_NODE_TYPES.Identifier) {
                return node.name;
            }
            if (node.type === experimental_utils_1.AST_NODE_TYPES.ThisExpression) {
                return 'this';
            }
            return getMemberExpressionText(node);
        }
        /**
         * Gets a normalized representation of the given MemberExpression
         */
        function getMemberExpressionText(node) {
            let objectText;
            // cases should match the list in ALLOWED_MEMBER_OBJECT_TYPES
            switch (node.object.type) {
                case experimental_utils_1.AST_NODE_TYPES.CallExpression:
                case experimental_utils_1.AST_NODE_TYPES.OptionalCallExpression:
                case experimental_utils_1.AST_NODE_TYPES.Identifier:
                    objectText = getText(node.object);
                    break;
                case experimental_utils_1.AST_NODE_TYPES.MemberExpression:
                case experimental_utils_1.AST_NODE_TYPES.OptionalMemberExpression:
                    objectText = getMemberExpressionText(node.object);
                    break;
                case experimental_utils_1.AST_NODE_TYPES.ThisExpression:
                    objectText = getText(node.object);
                    break;
                /* istanbul ignore next */
                default:
                    throw new Error(`Unexpected member object type: ${node.object.type}`);
            }
            let propertyText;
            if (node.computed) {
                // cases should match the list in ALLOWED_COMPUTED_PROP_TYPES
                switch (node.property.type) {
                    case experimental_utils_1.AST_NODE_TYPES.Identifier:
                        propertyText = getText(node.property);
                        break;
                    case experimental_utils_1.AST_NODE_TYPES.Literal:
                    case experimental_utils_1.AST_NODE_TYPES.BigIntLiteral:
                    case experimental_utils_1.AST_NODE_TYPES.TemplateLiteral:
                        propertyText = sourceCode.getText(node.property);
                        break;
                    case experimental_utils_1.AST_NODE_TYPES.MemberExpression:
                    case experimental_utils_1.AST_NODE_TYPES.OptionalMemberExpression:
                        propertyText = getMemberExpressionText(node.property);
                        break;
                    /* istanbul ignore next */
                    default:
                        throw new Error(`Unexpected member property type: ${node.object.type}`);
                }
                return `${objectText}${node.optional ? '?.' : ''}[${propertyText}]`;
            }
            else {
                // cases should match the list in ALLOWED_NON_COMPUTED_PROP_TYPES
                switch (node.property.type) {
                    case experimental_utils_1.AST_NODE_TYPES.Identifier:
                        propertyText = getText(node.property);
                        break;
                    /* istanbul ignore next */
                    default:
                        throw new Error(`Unexpected member property type: ${node.object.type}`);
                }
                return `${objectText}${node.optional ? '?.' : '.'}${propertyText}`;
            }
        }
    },
});
const ALLOWED_MEMBER_OBJECT_TYPES = new Set([
    experimental_utils_1.AST_NODE_TYPES.CallExpression,
    experimental_utils_1.AST_NODE_TYPES.Identifier,
    experimental_utils_1.AST_NODE_TYPES.MemberExpression,
    experimental_utils_1.AST_NODE_TYPES.OptionalCallExpression,
    experimental_utils_1.AST_NODE_TYPES.OptionalMemberExpression,
    experimental_utils_1.AST_NODE_TYPES.ThisExpression,
]);
const ALLOWED_COMPUTED_PROP_TYPES = new Set([
    experimental_utils_1.AST_NODE_TYPES.BigIntLiteral,
    experimental_utils_1.AST_NODE_TYPES.Identifier,
    experimental_utils_1.AST_NODE_TYPES.Literal,
    experimental_utils_1.AST_NODE_TYPES.MemberExpression,
    experimental_utils_1.AST_NODE_TYPES.OptionalMemberExpression,
    experimental_utils_1.AST_NODE_TYPES.TemplateLiteral,
]);
const ALLOWED_NON_COMPUTED_PROP_TYPES = new Set([
    experimental_utils_1.AST_NODE_TYPES.Identifier,
]);
function isValidChainTarget(node, allowIdentifier) {
    if (node.type === experimental_utils_1.AST_NODE_TYPES.MemberExpression ||
        node.type === experimental_utils_1.AST_NODE_TYPES.OptionalMemberExpression) {
        const isObjectValid = ALLOWED_MEMBER_OBJECT_TYPES.has(node.object.type) &&
            // make sure to validate the expression is of our expected structure
            isValidChainTarget(node.object, true);
        const isPropertyValid = node.computed
            ? ALLOWED_COMPUTED_PROP_TYPES.has(node.property.type) &&
                // make sure to validate the member expression is of our expected structure
                (node.property.type === experimental_utils_1.AST_NODE_TYPES.MemberExpression ||
                    node.property.type === experimental_utils_1.AST_NODE_TYPES.OptionalMemberExpression
                    ? isValidChainTarget(node.property, allowIdentifier)
                    : true)
            : ALLOWED_NON_COMPUTED_PROP_TYPES.has(node.property.type);
        return isObjectValid && isPropertyValid;
    }
    if (node.type === experimental_utils_1.AST_NODE_TYPES.CallExpression ||
        node.type === experimental_utils_1.AST_NODE_TYPES.OptionalCallExpression) {
        return isValidChainTarget(node.callee, allowIdentifier);
    }
    if (allowIdentifier &&
        (node.type === experimental_utils_1.AST_NODE_TYPES.Identifier ||
            node.type === experimental_utils_1.AST_NODE_TYPES.ThisExpression)) {
        return true;
    }
    /*
    special case for the following, where we only want the left
    - foo !== null
    - foo != null
    - foo !== undefined
    - foo != undefined
    */
    if (node.type === experimental_utils_1.AST_NODE_TYPES.BinaryExpression &&
        ['!==', '!='].includes(node.operator) &&
        isValidChainTarget(node.left, allowIdentifier)) {
        if (node.right.type === experimental_utils_1.AST_NODE_TYPES.Identifier &&
            node.right.name === 'undefined') {
            return true;
        }
        if (node.right.type === experimental_utils_1.AST_NODE_TYPES.Literal &&
            node.right.value === null) {
            return true;
        }
    }
    return false;
}
//# sourceMappingURL=prefer-optional-chain.js.map