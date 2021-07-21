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
const printNodeModifiers = (node, final) => {
    var _a;
    return `${(_a = node.accessibility) !== null && _a !== void 0 ? _a : ''}${node.static ? ' static' : ''} ${final} `.trimLeft();
};
const isSupportedLiteral = (node) => {
    if (node.type === experimental_utils_1.AST_NODE_TYPES.Literal ||
        node.type === experimental_utils_1.AST_NODE_TYPES.BigIntLiteral) {
        return true;
    }
    if (node.type === experimental_utils_1.AST_NODE_TYPES.TaggedTemplateExpression ||
        node.type === experimental_utils_1.AST_NODE_TYPES.TemplateLiteral) {
        return ('quasi' in node ? node.quasi.quasis : node.quasis).length === 1;
    }
    return false;
};
exports.default = util.createRule({
    name: 'class-literal-property-style',
    meta: {
        type: 'problem',
        docs: {
            description: 'Ensures that literals on classes are exposed in a consistent style',
            category: 'Best Practices',
            recommended: false,
        },
        fixable: 'code',
        messages: {
            preferFieldStyle: 'Literals should be exposed using readonly fields.',
            preferGetterStyle: 'Literals should be exposed using getters.',
        },
        schema: [{ enum: ['fields', 'getters'] }],
    },
    defaultOptions: ['fields'],
    create(context, [style]) {
        if (style === 'fields') {
            return {
                MethodDefinition(node) {
                    if (node.kind !== 'get' ||
                        !node.value.body ||
                        !node.value.body.body.length) {
                        return;
                    }
                    const [statement] = node.value.body.body;
                    if (statement.type !== experimental_utils_1.AST_NODE_TYPES.ReturnStatement) {
                        return;
                    }
                    const { argument } = statement;
                    if (!argument || !isSupportedLiteral(argument)) {
                        return;
                    }
                    context.report({
                        node: node.key,
                        messageId: 'preferFieldStyle',
                        fix(fixer) {
                            const sourceCode = context.getSourceCode();
                            const name = sourceCode.getText(node.key);
                            let text = '';
                            text += printNodeModifiers(node, 'readonly');
                            text += node.computed ? `[${name}]` : name;
                            text += ` = ${sourceCode.getText(argument)};`;
                            return fixer.replaceText(node, text);
                        },
                    });
                },
            };
        }
        return {
            ClassProperty(node) {
                if (!node.readonly || node.declare) {
                    return;
                }
                const { value } = node;
                if (!value || !isSupportedLiteral(value)) {
                    return;
                }
                context.report({
                    node: node.key,
                    messageId: 'preferGetterStyle',
                    fix(fixer) {
                        const sourceCode = context.getSourceCode();
                        const name = sourceCode.getText(node.key);
                        let text = '';
                        text += printNodeModifiers(node, 'get');
                        text += node.computed ? `[${name}]` : name;
                        text += `() { return ${sourceCode.getText(value)}; }`;
                        return fixer.replaceText(node, text);
                    },
                });
            },
        };
    },
});
//# sourceMappingURL=class-literal-property-style.js.map