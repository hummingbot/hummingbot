"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (Object.hasOwnProperty.call(mod, k)) result[k] = mod[k];
    result["default"] = mod;
    return result;
};
Object.defineProperty(exports, "__esModule", { value: true });
const experimental_utils_1 = require("@typescript-eslint/experimental-utils");
const no_unused_expressions_1 = __importDefault(require("eslint/lib/rules/no-unused-expressions"));
const util = __importStar(require("../util"));
exports.default = util.createRule({
    name: 'no-unused-expressions',
    meta: {
        type: 'suggestion',
        docs: {
            description: 'Disallow unused expressions',
            category: 'Best Practices',
            recommended: false,
            extendsBaseRule: true,
        },
        schema: no_unused_expressions_1.default.meta.schema,
        messages: no_unused_expressions_1.default.meta.messages,
    },
    defaultOptions: [],
    create(context) {
        const rules = no_unused_expressions_1.default.create(context);
        return {
            ExpressionStatement(node) {
                if (node.directive ||
                    node.expression.type === experimental_utils_1.AST_NODE_TYPES.OptionalCallExpression) {
                    return;
                }
                rules.ExpressionStatement(node);
            },
        };
    },
});
//# sourceMappingURL=no-unused-expressions.js.map