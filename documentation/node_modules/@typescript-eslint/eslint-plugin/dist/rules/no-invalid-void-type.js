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
    name: 'no-invalid-void-type',
    meta: {
        type: 'problem',
        docs: {
            description: 'Disallows usage of `void` type outside of generic or return types',
            category: 'Best Practices',
            recommended: false,
        },
        messages: {
            invalidVoidForGeneric: '{{ generic }} may not have void as a type variable',
            invalidVoidNotReturnOrGeneric: 'void is only valid as a return type or generic type variable',
            invalidVoidNotReturn: 'void is only valid as a return type',
        },
        schema: [
            {
                type: 'object',
                properties: {
                    allowInGenericTypeArguments: {
                        oneOf: [
                            { type: 'boolean' },
                            {
                                type: 'array',
                                items: { type: 'string' },
                                minLength: 1,
                            },
                        ],
                    },
                },
                additionalProperties: false,
            },
        ],
    },
    defaultOptions: [{ allowInGenericTypeArguments: true }],
    create(context, [{ allowInGenericTypeArguments }]) {
        const validParents = [
            experimental_utils_1.AST_NODE_TYPES.TSTypeAnnotation,
        ];
        const invalidGrandParents = [
            experimental_utils_1.AST_NODE_TYPES.TSPropertySignature,
            experimental_utils_1.AST_NODE_TYPES.CallExpression,
            experimental_utils_1.AST_NODE_TYPES.ClassProperty,
            experimental_utils_1.AST_NODE_TYPES.Identifier,
        ];
        const validUnionMembers = [
            experimental_utils_1.AST_NODE_TYPES.TSVoidKeyword,
            experimental_utils_1.AST_NODE_TYPES.TSNeverKeyword,
        ];
        if (allowInGenericTypeArguments === true) {
            validParents.push(experimental_utils_1.AST_NODE_TYPES.TSTypeParameterInstantiation);
        }
        /**
         * @brief check if the given void keyword is used as a valid generic type
         *
         * reports if the type parametrized by void is not in the whitelist, or
         * allowInGenericTypeArguments is false.
         * no-op if the given void keyword is not used as generic type
         */
        function checkGenericTypeArgument(node) {
            var _a, _b;
            // only matches T<..., void, ...>
            // extra check for precaution
            /* istanbul ignore next */
            if (((_a = node.parent) === null || _a === void 0 ? void 0 : _a.type) !== experimental_utils_1.AST_NODE_TYPES.TSTypeParameterInstantiation ||
                ((_b = node.parent.parent) === null || _b === void 0 ? void 0 : _b.type) !== experimental_utils_1.AST_NODE_TYPES.TSTypeReference) {
                return;
            }
            // check whitelist
            if (Array.isArray(allowInGenericTypeArguments)) {
                const sourceCode = context.getSourceCode();
                const fullyQualifiedName = sourceCode
                    .getText(node.parent.parent.typeName)
                    .replace(/ /gu, '');
                if (!allowInGenericTypeArguments
                    .map(s => s.replace(/ /gu, ''))
                    .includes(fullyQualifiedName)) {
                    context.report({
                        messageId: 'invalidVoidForGeneric',
                        data: { generic: fullyQualifiedName },
                        node,
                    });
                }
                return;
            }
            if (!allowInGenericTypeArguments) {
                context.report({
                    messageId: 'invalidVoidNotReturn',
                    node,
                });
            }
        }
        /**
         * @brief checks that a union containing void is valid
         * @return true if every member of the union is specified as a valid type in
         * validUnionMembers, or is a valid generic type parametrized by void
         */
        function isValidUnionType(node) {
            return node.types.every(member => {
                var _a, _b;
                return validUnionMembers.includes(member.type) ||
                    // allows any T<..., void, ...> here, checked by checkGenericTypeArgument
                    (member.type === experimental_utils_1.AST_NODE_TYPES.TSTypeReference &&
                        ((_a = member.typeParameters) === null || _a === void 0 ? void 0 : _a.type) ===
                            experimental_utils_1.AST_NODE_TYPES.TSTypeParameterInstantiation && ((_b = member.typeParameters) === null || _b === void 0 ? void 0 : _b.params.map(param => param.type).includes(experimental_utils_1.AST_NODE_TYPES.TSVoidKeyword)));
            });
        }
        return {
            TSVoidKeyword(node) {
                var _a;
                /* istanbul ignore next */
                if (!((_a = node.parent) === null || _a === void 0 ? void 0 : _a.parent)) {
                    return;
                }
                // checks T<..., void, ...> against specification of allowInGenericArguments option
                if (node.parent.type === experimental_utils_1.AST_NODE_TYPES.TSTypeParameterInstantiation &&
                    node.parent.parent.type === experimental_utils_1.AST_NODE_TYPES.TSTypeReference) {
                    checkGenericTypeArgument(node);
                    return;
                }
                // union w/ void must contain types from validUnionMembers, or a valid generic void type
                if (node.parent.type === experimental_utils_1.AST_NODE_TYPES.TSUnionType &&
                    isValidUnionType(node.parent)) {
                    return;
                }
                // default cases
                if (validParents.includes(node.parent.type) &&
                    !invalidGrandParents.includes(node.parent.parent.type)) {
                    return;
                }
                context.report({
                    messageId: allowInGenericTypeArguments
                        ? 'invalidVoidNotReturnOrGeneric'
                        : 'invalidVoidNotReturn',
                    node,
                });
            },
        };
    },
});
//# sourceMappingURL=no-invalid-void-type.js.map