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
    name: 'no-unsafe-member-access',
    meta: {
        type: 'problem',
        docs: {
            description: 'Disallows member access on any typed variables',
            category: 'Possible Errors',
            recommended: false,
            requiresTypeChecking: true,
        },
        messages: {
            unsafeMemberExpression: 'Unsafe member access {{property}} on an any value.',
            unsafeComputedMemberAccess: 'Computed name {{property}} resolves to an any value.',
        },
        schema: [],
    },
    defaultOptions: [],
    create(context) {
        const { program, esTreeNodeToTSNodeMap } = util.getParserServices(context);
        const checker = program.getTypeChecker();
        const sourceCode = context.getSourceCode();
        const stateCache = new Map();
        function checkMemberExpression(node) {
            const cachedState = stateCache.get(node);
            if (cachedState) {
                return cachedState;
            }
            if (util.isMemberOrOptionalMemberExpression(node.object)) {
                const objectState = checkMemberExpression(node.object);
                if (objectState === 1 /* Unsafe */) {
                    // if the object is unsafe, we know this will be unsafe as well
                    // we don't need to report, as we have already reported on the inner member expr
                    stateCache.set(node, objectState);
                    return objectState;
                }
            }
            const tsNode = esTreeNodeToTSNodeMap.get(node.object);
            const type = checker.getTypeAtLocation(tsNode);
            const state = util.isTypeAnyType(type) ? 1 /* Unsafe */ : 2 /* Safe */;
            stateCache.set(node, state);
            if (state === 1 /* Unsafe */) {
                const propertyName = sourceCode.getText(node.property);
                context.report({
                    node,
                    messageId: 'unsafeMemberExpression',
                    data: {
                        property: node.computed ? `[${propertyName}]` : `.${propertyName}`,
                    },
                });
            }
            return state;
        }
        return {
            'MemberExpression, OptionalMemberExpression': checkMemberExpression,
            ':matches(MemberExpression, OptionalMemberExpression)[computed = true] > *.property'(node) {
                if (
                // x[1]
                node.type === experimental_utils_1.AST_NODE_TYPES.Literal ||
                    // x[1++] x[++x] etc
                    // FUN FACT - **all** update expressions return type number, regardless of the argument's type,
                    // because JS engines return NaN if there the argument is not a number.
                    node.type === experimental_utils_1.AST_NODE_TYPES.UpdateExpression) {
                    // perf optimizations - literals can obviously never be `any`
                    return;
                }
                const tsNode = esTreeNodeToTSNodeMap.get(node);
                const type = checker.getTypeAtLocation(tsNode);
                if (util.isTypeAnyType(type)) {
                    const propertyName = sourceCode.getText(node);
                    context.report({
                        node,
                        messageId: 'unsafeComputedMemberAccess',
                        data: {
                            property: `[${propertyName}]`,
                        },
                    });
                }
            },
        };
    },
});
//# sourceMappingURL=no-unsafe-member-access.js.map