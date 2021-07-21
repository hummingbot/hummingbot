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
exports.default = util.createRule({
    name: 'no-unsafe-call',
    meta: {
        type: 'problem',
        docs: {
            description: 'Disallows calling an any type value',
            category: 'Possible Errors',
            recommended: false,
            requiresTypeChecking: true,
        },
        messages: {
            unsafeCall: 'Unsafe call of an any typed value.',
            unsafeNew: 'Unsafe construction of an any type value.',
            unsafeTemplateTag: 'Unsafe any typed template tag.',
        },
        schema: [],
    },
    defaultOptions: [],
    create(context) {
        const { program, esTreeNodeToTSNodeMap } = util.getParserServices(context);
        const checker = program.getTypeChecker();
        function checkCall(node, reportingNode, messageId) {
            const tsNode = esTreeNodeToTSNodeMap.get(node);
            const type = util.getConstrainedTypeAtLocation(checker, tsNode);
            if (util.isTypeAnyType(type)) {
                context.report({
                    node: reportingNode,
                    messageId: messageId,
                });
            }
        }
        return {
            ':matches(CallExpression, OptionalCallExpression) > :not(Import).callee'(node) {
                checkCall(node, node, 'unsafeCall');
            },
            NewExpression(node) {
                checkCall(node.callee, node, 'unsafeNew');
            },
            'TaggedTemplateExpression > *.tag'(node) {
                checkCall(node, node, 'unsafeTemplateTag');
            },
        };
    },
});
//# sourceMappingURL=no-unsafe-call.js.map