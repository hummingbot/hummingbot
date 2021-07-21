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
const tsutils_1 = require("tsutils");
const ts = __importStar(require("typescript"));
const util = __importStar(require("../util"));
exports.default = util.createRule({
    name: 'no-unnecessary-type-assertion',
    meta: {
        docs: {
            description: 'Warns if a type assertion does not change the type of an expression',
            category: 'Best Practices',
            recommended: 'error',
            requiresTypeChecking: true,
        },
        fixable: 'code',
        messages: {
            unnecessaryAssertion: 'This assertion is unnecessary since it does not change the type of the expression.',
            contextuallyUnnecessary: 'This assertion is unnecessary since the receiver accepts the original type of the expression.',
        },
        schema: [
            {
                type: 'object',
                properties: {
                    typesToIgnore: {
                        type: 'array',
                        items: {
                            type: 'string',
                        },
                    },
                },
            },
        ],
        type: 'suggestion',
    },
    defaultOptions: [{}],
    create(context, [options]) {
        const sourceCode = context.getSourceCode();
        const parserServices = util.getParserServices(context);
        const checker = parserServices.program.getTypeChecker();
        const compilerOptions = parserServices.program.getCompilerOptions();
        /**
         * Sometimes tuple types don't have ObjectFlags.Tuple set, like when they're being matched against an inferred type.
         * So, in addition, check if there are integer properties 0..n and no other numeric keys
         */
        function couldBeTupleType(type) {
            const properties = type.getProperties();
            if (properties.length === 0) {
                return false;
            }
            let i = 0;
            for (; i < properties.length; ++i) {
                const name = properties[i].name;
                if (String(i) !== name) {
                    if (i === 0) {
                        // if there are no integer properties, this is not a tuple
                        return false;
                    }
                    break;
                }
            }
            for (; i < properties.length; ++i) {
                if (String(+properties[i].name) === properties[i].name) {
                    return false; // if there are any other numeric properties, this is not a tuple
                }
            }
            return true;
        }
        /**
         * Returns true if there's a chance the variable has been used before a value has been assigned to it
         */
        function isPossiblyUsedBeforeAssigned(node) {
            const declaration = util.getDeclaration(checker, node);
            if (!declaration) {
                // don't know what the declaration is for some reason, so just assume the worst
                return true;
            }
            if (
            // non-strict mode doesn't care about used before assigned errors
            tsutils_1.isStrictCompilerOptionEnabled(compilerOptions, 'strictNullChecks') &&
                // ignore class properties as they are compile time guarded
                // also ignore function arguments as they can't be used before defined
                tsutils_1.isVariableDeclaration(declaration) &&
                // is it `const x!: number`
                declaration.initializer === undefined &&
                declaration.exclamationToken === undefined &&
                declaration.type !== undefined) {
                // check if the defined variable type has changed since assignment
                const declarationType = checker.getTypeFromTypeNode(declaration.type);
                const type = util.getConstrainedTypeAtLocation(checker, node);
                if (declarationType === type) {
                    // possibly used before assigned, so just skip it
                    // better to false negative and skip it, than false positive and fix to compile erroring code
                    //
                    // no better way to figure this out right now
                    // https://github.com/Microsoft/TypeScript/issues/31124
                    return true;
                }
            }
            return false;
        }
        function isConstAssertion(node) {
            return (node.type === experimental_utils_1.AST_NODE_TYPES.TSTypeReference &&
                node.typeName.type === experimental_utils_1.AST_NODE_TYPES.Identifier &&
                node.typeName.name === 'const');
        }
        return {
            TSNonNullExpression(node) {
                const originalNode = parserServices.esTreeNodeToTSNodeMap.get(node);
                const type = util.getConstrainedTypeAtLocation(checker, originalNode.expression);
                if (!util.isNullableType(type)) {
                    if (isPossiblyUsedBeforeAssigned(originalNode.expression)) {
                        return;
                    }
                    context.report({
                        node,
                        messageId: 'unnecessaryAssertion',
                        fix(fixer) {
                            return fixer.removeRange([
                                originalNode.expression.end,
                                originalNode.end,
                            ]);
                        },
                    });
                }
                else {
                    // we know it's a nullable type
                    // so figure out if the variable is used in a place that accepts nullable types
                    const contextualType = util.getContextualType(checker, originalNode);
                    if (contextualType) {
                        // in strict mode you can't assign null to undefined, so we have to make sure that
                        // the two types share a nullable type
                        const typeIncludesUndefined = util.isTypeFlagSet(type, ts.TypeFlags.Undefined);
                        const typeIncludesNull = util.isTypeFlagSet(type, ts.TypeFlags.Null);
                        const contextualTypeIncludesUndefined = util.isTypeFlagSet(contextualType, ts.TypeFlags.Undefined);
                        const contextualTypeIncludesNull = util.isTypeFlagSet(contextualType, ts.TypeFlags.Null);
                        // make sure that the parent accepts the same types
                        // i.e. assigning `string | null | undefined` to `string | undefined` is invalid
                        const isValidUndefined = typeIncludesUndefined
                            ? contextualTypeIncludesUndefined
                            : true;
                        const isValidNull = typeIncludesNull
                            ? contextualTypeIncludesNull
                            : true;
                        if (isValidUndefined && isValidNull) {
                            context.report({
                                node,
                                messageId: 'contextuallyUnnecessary',
                                fix(fixer) {
                                    return fixer.removeRange([
                                        originalNode.expression.end,
                                        originalNode.end,
                                    ]);
                                },
                            });
                        }
                    }
                }
            },
            'TSAsExpression, TSTypeAssertion'(node) {
                var _a;
                if (((_a = options.typesToIgnore) === null || _a === void 0 ? void 0 : _a.includes(sourceCode.getText(node.typeAnnotation))) ||
                    isConstAssertion(node.typeAnnotation)) {
                    return;
                }
                const originalNode = parserServices.esTreeNodeToTSNodeMap.get(node);
                const castType = checker.getTypeAtLocation(originalNode);
                if (tsutils_1.isTypeFlagSet(castType, ts.TypeFlags.Literal) ||
                    (tsutils_1.isObjectType(castType) &&
                        (tsutils_1.isObjectFlagSet(castType, ts.ObjectFlags.Tuple) ||
                            couldBeTupleType(castType)))) {
                    // It's not always safe to remove a cast to a literal type or tuple
                    // type, as those types are sometimes widened without the cast.
                    return;
                }
                const uncastType = checker.getTypeAtLocation(originalNode.expression);
                if (uncastType === castType) {
                    context.report({
                        node,
                        messageId: 'unnecessaryAssertion',
                        fix(fixer) {
                            return originalNode.kind === ts.SyntaxKind.TypeAssertionExpression
                                ? fixer.removeRange([
                                    originalNode.getStart(),
                                    originalNode.expression.getStart(),
                                ])
                                : fixer.removeRange([
                                    originalNode.expression.end,
                                    originalNode.end,
                                ]);
                        },
                    });
                }
                // TODO - add contextually unnecessary check for this
            },
        };
    },
});
//# sourceMappingURL=no-unnecessary-type-assertion.js.map