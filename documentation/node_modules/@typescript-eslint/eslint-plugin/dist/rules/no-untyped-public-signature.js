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
const experimental_utils_1 = require("@typescript-eslint/experimental-utils");
exports.default = util.createRule({
    name: 'no-untyped-public-signature',
    meta: {
        deprecated: true,
        replacedBy: ['explicit-module-boundary-types'],
        docs: {
            description: 'Disallow untyped public methods',
            category: 'Best Practices',
            recommended: false,
        },
        messages: {
            noReturnType: 'Public method has no return type.',
            untypedParameter: 'Public method parameters should be typed.',
        },
        schema: [
            {
                allowAdditionalProperties: false,
                properties: {
                    ignoredMethods: {
                        type: 'array',
                        items: {
                            type: 'string',
                        },
                    },
                },
                type: 'object',
            },
        ],
        type: 'suggestion',
    },
    defaultOptions: [{ ignoredMethods: [] }],
    create(context, [options]) {
        const ignoredMethods = new Set(options.ignoredMethods);
        function isPublicMethod(node) {
            return node.accessibility === 'public' || !node.accessibility;
        }
        function isIgnoredMethod(node, ignoredMethods) {
            if (node.key.type === experimental_utils_1.AST_NODE_TYPES.Literal &&
                typeof node.key.value === 'string') {
                return ignoredMethods.has(node.key.value);
            }
            if (node.key.type === experimental_utils_1.AST_NODE_TYPES.TemplateLiteral &&
                node.key.expressions.length === 0) {
                return ignoredMethods.has(node.key.quasis[0].value.raw);
            }
            if (!node.computed && node.key.type === experimental_utils_1.AST_NODE_TYPES.Identifier) {
                return ignoredMethods.has(node.key.name);
            }
            return false;
        }
        function isParamTyped(node) {
            return (!!node.typeAnnotation &&
                node.typeAnnotation.typeAnnotation.type !== experimental_utils_1.AST_NODE_TYPES.TSAnyKeyword);
        }
        function isReturnTyped(node) {
            if (!node) {
                return false;
            }
            return (node.typeAnnotation &&
                node.typeAnnotation.type !== experimental_utils_1.AST_NODE_TYPES.TSAnyKeyword);
        }
        return {
            'TSAbstractMethodDefinition, MethodDefinition'(node) {
                if (isPublicMethod(node) && !isIgnoredMethod(node, ignoredMethods)) {
                    const paramIdentifiers = node.value.params.filter(param => param.type === experimental_utils_1.AST_NODE_TYPES.Identifier);
                    const identifiersHaveTypes = paramIdentifiers.every(isParamTyped);
                    if (!identifiersHaveTypes) {
                        context.report({
                            node,
                            messageId: 'untypedParameter',
                            data: {},
                        });
                    }
                    if (node.kind !== 'constructor' &&
                        node.kind !== 'set' &&
                        !isReturnTyped(node.value.returnType)) {
                        context.report({
                            node,
                            messageId: 'noReturnType',
                            data: {},
                        });
                    }
                }
            },
        };
    },
});
//# sourceMappingURL=no-untyped-public-signature.js.map