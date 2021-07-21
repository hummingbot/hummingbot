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
const getMemberExpressionName = (member) => {
    if (!member.computed) {
        return member.property.name;
    }
    if (member.property.type === experimental_utils_1.AST_NODE_TYPES.Literal &&
        typeof member.property.value === 'string') {
        return member.property.value;
    }
    return null;
};
exports.default = util.createRule({
    name: 'prefer-reduce-type-parameter',
    meta: {
        type: 'problem',
        docs: {
            category: 'Best Practices',
            recommended: false,
            description: 'Prefer using type parameter when calling `Array#reduce` instead of casting',
            requiresTypeChecking: true,
        },
        messages: {
            preferTypeParameter: 'Unnecessary cast: Array#reduce accepts a type parameter for the default value.',
        },
        fixable: 'code',
        schema: [],
    },
    defaultOptions: [],
    create(context) {
        const service = util.getParserServices(context);
        const checker = service.program.getTypeChecker();
        return {
            ':matches(CallExpression, OptionalCallExpression) > :matches(MemberExpression, OptionalMemberExpression).callee'(callee) {
                if (getMemberExpressionName(callee) !== 'reduce') {
                    return;
                }
                const [, secondArg] = callee.parent.arguments;
                if (callee.parent.arguments.length < 2 ||
                    !util.isTypeAssertion(secondArg)) {
                    return;
                }
                // Get the symbol of the `reduce` method.
                const tsNode = service.esTreeNodeToTSNodeMap.get(callee.object);
                const calleeObjType = util.getConstrainedTypeAtLocation(checker, tsNode);
                // Check the owner type of the `reduce` method.
                if (checker.isArrayType(calleeObjType)) {
                    context.report({
                        messageId: 'preferTypeParameter',
                        node: secondArg,
                        fix: fixer => [
                            fixer.removeRange([
                                secondArg.range[0],
                                secondArg.expression.range[0],
                            ]),
                            fixer.removeRange([
                                secondArg.expression.range[1],
                                secondArg.range[1],
                            ]),
                            fixer.insertTextAfter(callee, `<${context
                                .getSourceCode()
                                .getText(secondArg.typeAnnotation)}>`),
                        ],
                    });
                    return;
                }
            },
        };
    },
});
//# sourceMappingURL=prefer-reduce-type-parameter.js.map