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
/**
 * Check whatever node can be considered as simple
 * @param node the node to be evaluated.
 */
function isSimpleType(node) {
    switch (node.type) {
        case experimental_utils_1.AST_NODE_TYPES.Identifier:
        case experimental_utils_1.AST_NODE_TYPES.TSAnyKeyword:
        case experimental_utils_1.AST_NODE_TYPES.TSBooleanKeyword:
        case experimental_utils_1.AST_NODE_TYPES.TSNeverKeyword:
        case experimental_utils_1.AST_NODE_TYPES.TSNumberKeyword:
        case experimental_utils_1.AST_NODE_TYPES.TSObjectKeyword:
        case experimental_utils_1.AST_NODE_TYPES.TSStringKeyword:
        case experimental_utils_1.AST_NODE_TYPES.TSSymbolKeyword:
        case experimental_utils_1.AST_NODE_TYPES.TSUnknownKeyword:
        case experimental_utils_1.AST_NODE_TYPES.TSVoidKeyword:
        case experimental_utils_1.AST_NODE_TYPES.TSNullKeyword:
        case experimental_utils_1.AST_NODE_TYPES.TSArrayType:
        case experimental_utils_1.AST_NODE_TYPES.TSUndefinedKeyword:
        case experimental_utils_1.AST_NODE_TYPES.TSThisType:
        case experimental_utils_1.AST_NODE_TYPES.TSQualifiedName:
            return true;
        case experimental_utils_1.AST_NODE_TYPES.TSTypeReference:
            if (node.typeName &&
                node.typeName.type === experimental_utils_1.AST_NODE_TYPES.Identifier &&
                node.typeName.name === 'Array') {
                if (!node.typeParameters) {
                    return true;
                }
                if (node.typeParameters.params.length === 1) {
                    return isSimpleType(node.typeParameters.params[0]);
                }
            }
            else {
                if (node.typeParameters) {
                    return false;
                }
                return isSimpleType(node.typeName);
            }
            return false;
        default:
            return false;
    }
}
/**
 * Check if node needs parentheses
 * @param node the node to be evaluated.
 */
function typeNeedsParentheses(node) {
    switch (node.type) {
        case experimental_utils_1.AST_NODE_TYPES.TSTypeReference:
            return typeNeedsParentheses(node.typeName);
        case experimental_utils_1.AST_NODE_TYPES.TSUnionType:
        case experimental_utils_1.AST_NODE_TYPES.TSFunctionType:
        case experimental_utils_1.AST_NODE_TYPES.TSIntersectionType:
        case experimental_utils_1.AST_NODE_TYPES.TSTypeOperator:
        case experimental_utils_1.AST_NODE_TYPES.TSInferType:
            return true;
        case experimental_utils_1.AST_NODE_TYPES.Identifier:
            return node.name === 'ReadonlyArray';
        default:
            return false;
    }
}
const arrayOption = { enum: ['array', 'generic', 'array-simple'] };
exports.default = util.createRule({
    name: 'array-type',
    meta: {
        type: 'suggestion',
        docs: {
            description: 'Requires using either `T[]` or `Array<T>` for arrays',
            category: 'Stylistic Issues',
            // too opinionated to be recommended
            recommended: false,
        },
        fixable: 'code',
        messages: {
            errorStringGeneric: "Array type using '{{type}}[]' is forbidden. Use 'Array<{{type}}>' instead.",
            errorStringGenericSimple: "Array type using '{{type}}[]' is forbidden for non-simple types. Use 'Array<{{type}}>' instead.",
            errorStringArray: "Array type using 'Array<{{type}}>' is forbidden. Use '{{type}}[]' instead.",
            errorStringArraySimple: "Array type using 'Array<{{type}}>' is forbidden for simple types. Use '{{type}}[]' instead.",
        },
        schema: [
            {
                type: 'object',
                properties: {
                    default: arrayOption,
                    readonly: arrayOption,
                },
            },
        ],
    },
    defaultOptions: [
        {
            default: 'array',
        },
    ],
    create(context, [options]) {
        var _a;
        const sourceCode = context.getSourceCode();
        const defaultOption = options.default;
        const readonlyOption = (_a = options.readonly) !== null && _a !== void 0 ? _a : defaultOption;
        const isArraySimpleOption = defaultOption === 'array-simple' && readonlyOption === 'array-simple';
        const isArrayOption = defaultOption === 'array' && readonlyOption === 'array';
        const isGenericOption = defaultOption === 'generic' && readonlyOption === 'generic';
        /**
         * Check if whitespace is needed before this node
         * @param node the node to be evaluated.
         */
        function requireWhitespaceBefore(node) {
            const prevToken = sourceCode.getTokenBefore(node);
            if (!prevToken) {
                return false;
            }
            const nextToken = sourceCode.getTokenAfter(prevToken);
            if (nextToken && sourceCode.isSpaceBetweenTokens(prevToken, nextToken)) {
                return false;
            }
            return prevToken.type === experimental_utils_1.AST_TOKEN_TYPES.Identifier;
        }
        /**
         * @param node the node to be evaluated.
         */
        function getMessageType(node) {
            if (node) {
                if (node.type === experimental_utils_1.AST_NODE_TYPES.TSParenthesizedType) {
                    return getMessageType(node.typeAnnotation);
                }
                if (isSimpleType(node)) {
                    return sourceCode.getText(node);
                }
            }
            return 'T';
        }
        /**
         * @param node the node to be evaluated
         */
        function getTypeOpNodeRange(node) {
            if (!node) {
                return undefined;
            }
            const firstToken = sourceCode.getFirstToken(node);
            const nextToken = sourceCode.getTokenAfter(firstToken);
            return [firstToken.range[0], nextToken.range[0]];
        }
        return {
            TSArrayType(node) {
                if (isArrayOption ||
                    (isArraySimpleOption && isSimpleType(node.elementType))) {
                    return;
                }
                const isReadonly = node.parent &&
                    node.parent.type === experimental_utils_1.AST_NODE_TYPES.TSTypeOperator &&
                    node.parent.operator === 'readonly';
                const isReadonlyGeneric = readonlyOption === 'generic' && defaultOption !== 'generic';
                const isReadonlyArray = readonlyOption !== 'generic' && defaultOption === 'generic';
                if ((isReadonlyGeneric && !isReadonly) ||
                    (isReadonlyArray && isReadonly)) {
                    return;
                }
                const messageId = defaultOption === 'generic'
                    ? 'errorStringGeneric'
                    : 'errorStringGenericSimple';
                const typeOpNode = isReadonly ? node.parent : null;
                context.report({
                    node: isReadonly ? node.parent : node,
                    messageId,
                    data: {
                        type: getMessageType(node.elementType),
                    },
                    fix(fixer) {
                        const toFix = [
                            fixer.replaceTextRange([node.range[1] - 2, node.range[1]], '>'),
                        ];
                        const startText = requireWhitespaceBefore(node);
                        const typeOpNodeRange = getTypeOpNodeRange(typeOpNode);
                        if (typeOpNodeRange) {
                            toFix.unshift(fixer.removeRange(typeOpNodeRange));
                        }
                        else {
                            toFix.push(fixer.insertTextBefore(node, `${startText ? ' ' : ''}`));
                        }
                        toFix.push(fixer.insertTextBefore(node, `${isReadonly ? 'Readonly' : ''}Array<`));
                        if (node.elementType.type === experimental_utils_1.AST_NODE_TYPES.TSParenthesizedType) {
                            const first = sourceCode.getFirstToken(node.elementType);
                            const last = sourceCode.getLastToken(node.elementType);
                            if (!first || !last) {
                                return null;
                            }
                            toFix.push(fixer.remove(first));
                            toFix.push(fixer.remove(last));
                        }
                        return toFix;
                    },
                });
            },
            TSTypeReference(node) {
                if (isGenericOption ||
                    node.typeName.type !== experimental_utils_1.AST_NODE_TYPES.Identifier) {
                    return;
                }
                const isReadonlyArrayType = node.typeName.name === 'ReadonlyArray';
                const isArrayType = node.typeName.name === 'Array';
                if (!(isArrayType || isReadonlyArrayType) ||
                    (readonlyOption === 'generic' && isReadonlyArrayType) ||
                    (defaultOption === 'generic' && !isReadonlyArrayType)) {
                    return;
                }
                const readonlyPrefix = isReadonlyArrayType ? 'readonly ' : '';
                const typeParams = node.typeParameters && node.typeParameters.params;
                const messageId = defaultOption === 'array'
                    ? 'errorStringArray'
                    : 'errorStringArraySimple';
                if (!typeParams || typeParams.length === 0) {
                    // Create an 'any' array
                    context.report({
                        node,
                        messageId,
                        data: {
                            type: 'any',
                        },
                        fix(fixer) {
                            return fixer.replaceText(node, `${readonlyPrefix}any[]`);
                        },
                    });
                    return;
                }
                if (typeParams.length !== 1 ||
                    (defaultOption === 'array-simple' && !isSimpleType(typeParams[0]))) {
                    return;
                }
                const type = typeParams[0];
                const parens = typeNeedsParentheses(type);
                context.report({
                    node,
                    messageId,
                    data: {
                        type: getMessageType(type),
                    },
                    fix(fixer) {
                        return [
                            fixer.replaceTextRange([node.range[0], type.range[0]], `${readonlyPrefix}${parens ? '(' : ''}`),
                            fixer.replaceTextRange([type.range[1], node.range[1]], parens ? ')[]' : '[]'),
                        ];
                    },
                });
            },
        };
    },
});
//# sourceMappingURL=array-type.js.map