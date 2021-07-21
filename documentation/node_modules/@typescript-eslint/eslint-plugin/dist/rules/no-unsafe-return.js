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
const util = __importStar(require("../util"));
exports.default = util.createRule({
    name: 'no-unsafe-return',
    meta: {
        type: 'problem',
        docs: {
            description: 'Disallows returning any from a function',
            category: 'Possible Errors',
            recommended: false,
            requiresTypeChecking: true,
        },
        messages: {
            unsafeReturn: 'Unsafe return of an {{type}} typed value',
            unsafeReturnAssignment: 'Unsafe return of type {{sender}} from function with return type {{receiver}}.',
        },
        schema: [],
    },
    defaultOptions: [],
    create(context) {
        const { program, esTreeNodeToTSNodeMap } = util.getParserServices(context);
        const checker = program.getTypeChecker();
        function getParentFunctionNode(node) {
            let current = node.parent;
            while (current) {
                if (current.type === experimental_utils_1.AST_NODE_TYPES.ArrowFunctionExpression ||
                    current.type === experimental_utils_1.AST_NODE_TYPES.FunctionDeclaration ||
                    current.type === experimental_utils_1.AST_NODE_TYPES.FunctionExpression) {
                    return current;
                }
                current = current.parent;
            }
            // this shouldn't happen in correct code, but someone may attempt to parse bad code
            // the parser won't error, so we shouldn't throw here
            /* istanbul ignore next */ return null;
        }
        function checkReturn(returnNode, reportingNode = returnNode) {
            const tsNode = esTreeNodeToTSNodeMap.get(returnNode);
            const anyType = util.isAnyOrAnyArrayTypeDiscriminated(tsNode, checker);
            if (anyType !== 2 /* Safe */) {
                return context.report({
                    node: reportingNode,
                    messageId: 'unsafeReturn',
                    data: {
                        type: anyType === 0 /* Any */ ? 'any' : 'any[]',
                    },
                });
            }
            const functionNode = getParentFunctionNode(returnNode);
            /* istanbul ignore if */ if (!functionNode) {
                return;
            }
            // function has an explicit return type, so ensure it's a safe return
            const returnNodeType = util.getConstrainedTypeAtLocation(checker, esTreeNodeToTSNodeMap.get(returnNode));
            const functionTSNode = esTreeNodeToTSNodeMap.get(functionNode);
            // function expressions will not have their return type modified based on receiver typing
            // so we have to use the contextual typing in these cases, i.e.
            // const foo1: () => Set<string> = () => new Set<any>();
            // the return type of the arrow function is Set<any> even though the variable is typed as Set<string>
            let functionType = tsutils_1.isExpression(functionTSNode)
                ? util.getContextualType(checker, functionTSNode)
                : checker.getTypeAtLocation(functionTSNode);
            if (!functionType) {
                functionType = checker.getTypeAtLocation(functionTSNode);
            }
            for (const signature of functionType.getCallSignatures()) {
                const functionReturnType = signature.getReturnType();
                if (returnNodeType === functionReturnType) {
                    // don't bother checking if they're the same
                    // either the function is explicitly declared to return the same type
                    // or there was no declaration, so the return type is implicit
                    return;
                }
                const result = util.isUnsafeAssignment(returnNodeType, functionReturnType, checker);
                if (!result) {
                    return;
                }
                const { sender, receiver } = result;
                return context.report({
                    node: reportingNode,
                    messageId: 'unsafeReturnAssignment',
                    data: {
                        sender: checker.typeToString(sender),
                        receiver: checker.typeToString(receiver),
                    },
                });
            }
        }
        return {
            ReturnStatement(node) {
                const argument = node.argument;
                if (!argument) {
                    return;
                }
                checkReturn(argument, node);
            },
            'ArrowFunctionExpression > :not(BlockStatement).body': checkReturn,
        };
    },
});
//# sourceMappingURL=no-unsafe-return.js.map