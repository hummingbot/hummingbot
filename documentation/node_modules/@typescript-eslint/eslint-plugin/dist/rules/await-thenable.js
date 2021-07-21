"use strict";
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (Object.hasOwnProperty.call(mod, k)) result[k] = mod[k];
    result["default"] = mod;
    return result;
};
Object.defineProperty(exports, "__esModule", { value: true });
const tsutils = __importStar(require("tsutils"));
const ts = __importStar(require("typescript"));
const util = __importStar(require("../util"));
exports.default = util.createRule({
    name: 'await-thenable',
    meta: {
        docs: {
            description: 'Disallows awaiting a value that is not a Thenable',
            category: 'Best Practices',
            recommended: 'error',
            requiresTypeChecking: true,
        },
        messages: {
            await: 'Unexpected `await` of a non-Promise (non-"Thenable") value.',
        },
        schema: [],
        type: 'problem',
    },
    defaultOptions: [],
    create(context) {
        const parserServices = util.getParserServices(context);
        const checker = parserServices.program.getTypeChecker();
        return {
            AwaitExpression(node) {
                const originalNode = parserServices.esTreeNodeToTSNodeMap.get(node);
                const type = checker.getTypeAtLocation(originalNode.expression);
                if (!tsutils.isTypeFlagSet(type, ts.TypeFlags.Any) &&
                    !tsutils.isTypeFlagSet(type, ts.TypeFlags.Unknown) &&
                    !tsutils.isThenableType(checker, originalNode.expression, type)) {
                    context.report({
                        messageId: 'await',
                        node,
                    });
                }
            },
        };
    },
});
//# sourceMappingURL=await-thenable.js.map