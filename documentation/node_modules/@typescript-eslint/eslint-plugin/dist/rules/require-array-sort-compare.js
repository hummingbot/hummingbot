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
    name: 'require-array-sort-compare',
    defaultOptions: [],
    meta: {
        type: 'problem',
        docs: {
            description: 'Requires `Array#sort` calls to always provide a `compareFunction`',
            category: 'Best Practices',
            recommended: false,
            requiresTypeChecking: true,
        },
        messages: {
            requireCompare: "Require 'compare' argument.",
        },
        schema: [],
    },
    create(context) {
        const service = util.getParserServices(context);
        const checker = service.program.getTypeChecker();
        return {
            ":matches(CallExpression, OptionalCallExpression)[arguments.length=0] > :matches(MemberExpression, OptionalMemberExpression)[property.name='sort'][computed=false]"(callee) {
                const tsNode = service.esTreeNodeToTSNodeMap.get(callee.object);
                const calleeObjType = util.getConstrainedTypeAtLocation(checker, tsNode);
                if (util.isTypeArrayTypeOrUnionOfArrayTypes(calleeObjType, checker)) {
                    context.report({ node: callee.parent, messageId: 'requireCompare' });
                }
            },
        };
    },
});
//# sourceMappingURL=require-array-sort-compare.js.map