"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const experimental_utils_1 = require("@typescript-eslint/experimental-utils");
const no_invalid_this_1 = __importDefault(require("eslint/lib/rules/no-invalid-this"));
const util_1 = require("../util");
exports.default = util_1.createRule({
    name: 'no-invalid-this',
    meta: {
        type: 'suggestion',
        docs: {
            description: 'disallow `this` keywords outside of classes or class-like objects',
            category: 'Best Practices',
            recommended: false,
            extendsBaseRule: true,
        },
        messages: no_invalid_this_1.default.meta.messages,
        schema: no_invalid_this_1.default.meta.schema,
    },
    defaultOptions: [{ capIsConstructor: true }],
    create(context) {
        const rules = no_invalid_this_1.default.create(context);
        const argList = [];
        return Object.assign(Object.assign({}, rules), { FunctionDeclaration(node) {
                argList.push(node.params.some(param => param.type === experimental_utils_1.AST_NODE_TYPES.Identifier && param.name === 'this'));
                // baseRule's work
                rules.FunctionDeclaration(node);
            },
            'FunctionDeclaration:exit'(node) {
                argList.pop();
                // baseRule's work
                rules['FunctionDeclaration:exit'](node);
            },
            FunctionExpression(node) {
                argList.push(node.params.some(param => param.type === experimental_utils_1.AST_NODE_TYPES.Identifier && param.name === 'this'));
                // baseRule's work
                rules.FunctionExpression(node);
            },
            'FunctionExpression:exit'(node) {
                argList.pop();
                // baseRule's work
                rules['FunctionExpression:exit'](node);
            },
            ThisExpression(node) {
                const lastFnArg = argList[argList.length - 1];
                if (lastFnArg) {
                    return;
                }
                // baseRule's work
                rules.ThisExpression(node);
            } });
    },
});
//# sourceMappingURL=no-invalid-this.js.map