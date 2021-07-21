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
    name: 'no-extra-non-null-assertion',
    meta: {
        type: 'problem',
        docs: {
            description: 'Disallow extra non-null assertion',
            category: 'Stylistic Issues',
            recommended: false,
        },
        fixable: 'code',
        schema: [],
        messages: {
            noExtraNonNullAssertion: 'Forbidden extra non-null assertion.',
        },
    },
    defaultOptions: [],
    create(context) {
        function checkExtraNonNullAssertion(node) {
            context.report({
                node,
                messageId: 'noExtraNonNullAssertion',
                fix(fixer) {
                    return fixer.removeRange([node.range[1] - 1, node.range[1]]);
                },
            });
        }
        return {
            'TSNonNullExpression > TSNonNullExpression': checkExtraNonNullAssertion,
            'OptionalMemberExpression > TSNonNullExpression': checkExtraNonNullAssertion,
            'OptionalCallExpression > TSNonNullExpression.callee': checkExtraNonNullAssertion,
        };
    },
});
//# sourceMappingURL=no-extra-non-null-assertion.js.map