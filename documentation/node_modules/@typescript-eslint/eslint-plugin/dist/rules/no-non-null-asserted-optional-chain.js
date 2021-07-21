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
    name: 'no-non-null-asserted-optional-chain',
    meta: {
        type: 'problem',
        docs: {
            description: 'Disallows using a non-null assertion after an optional chain expression',
            category: 'Possible Errors',
            recommended: false,
            suggestion: true,
        },
        messages: {
            noNonNullOptionalChain: 'Optional chain expressions can return undefined by design - using a non-null assertion is unsafe and wrong.',
            suggestRemovingNonNull: 'You should remove the non-null assertion.',
        },
        schema: [],
    },
    defaultOptions: [],
    create(context) {
        return {
            'TSNonNullExpression > :matches(OptionalMemberExpression, OptionalCallExpression)'(node) {
                // selector guarantees this assertion
                const parent = node.parent;
                context.report({
                    node,
                    messageId: 'noNonNullOptionalChain',
                    // use a suggestion instead of a fixer, because this can obviously break type checks
                    suggest: [
                        {
                            messageId: 'suggestRemovingNonNull',
                            fix(fixer) {
                                return fixer.removeRange([
                                    parent.range[1] - 1,
                                    parent.range[1],
                                ]);
                            },
                        },
                    ],
                });
            },
        };
    },
});
//# sourceMappingURL=no-non-null-asserted-optional-chain.js.map