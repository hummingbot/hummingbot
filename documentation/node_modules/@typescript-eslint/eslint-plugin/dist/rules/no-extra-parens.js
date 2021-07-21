"use strict";
// any is required to work around manipulating the AST in weird ways
/* eslint-disable @typescript-eslint/no-explicit-any */
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
const no_extra_parens_1 = __importDefault(require("eslint/lib/rules/no-extra-parens"));
const util = __importStar(require("../util"));
exports.default = util.createRule({
    name: 'no-extra-parens',
    meta: {
        type: 'layout',
        docs: {
            description: 'Disallow unnecessary parentheses',
            category: 'Possible Errors',
            recommended: false,
            extendsBaseRule: true,
        },
        fixable: 'code',
        schema: no_extra_parens_1.default.meta.schema,
        messages: no_extra_parens_1.default.meta.messages,
    },
    defaultOptions: ['all'],
    create(context) {
        const rules = no_extra_parens_1.default.create(context);
        function binaryExp(node) {
            const rule = rules.BinaryExpression;
            // makes the rule think it should skip the left or right
            const isLeftTypeAssertion = util.isTypeAssertion(node.left);
            const isRightTypeAssertion = util.isTypeAssertion(node.right);
            if (isLeftTypeAssertion && isRightTypeAssertion) {
                return; // ignore
            }
            if (isLeftTypeAssertion) {
                return rule(Object.assign(Object.assign({}, node), { left: Object.assign(Object.assign({}, node.left), { type: experimental_utils_1.AST_NODE_TYPES.SequenceExpression }) }));
            }
            if (isRightTypeAssertion) {
                return rule(Object.assign(Object.assign({}, node), { right: Object.assign(Object.assign({}, node.right), { type: experimental_utils_1.AST_NODE_TYPES.SequenceExpression }) }));
            }
            return rule(node);
        }
        function callExp(node) {
            const rule = rules.CallExpression;
            if (util.isTypeAssertion(node.callee)) {
                // reduces the precedence of the node so the rule thinks it needs to be wrapped
                return rule(Object.assign(Object.assign({}, node), { callee: Object.assign(Object.assign({}, node.callee), { type: experimental_utils_1.AST_NODE_TYPES.SequenceExpression }) }));
            }
            return rule(node);
        }
        function unaryUpdateExpression(node) {
            const rule = rules.UnaryExpression;
            if (util.isTypeAssertion(node.argument)) {
                // reduces the precedence of the node so the rule thinks it needs to be wrapped
                return rule(Object.assign(Object.assign({}, node), { argument: Object.assign(Object.assign({}, node.argument), { type: experimental_utils_1.AST_NODE_TYPES.SequenceExpression }) }));
            }
            return rule(node);
        }
        const overrides = {
            // ArrayExpression
            ArrowFunctionExpression(node) {
                if (!util.isTypeAssertion(node.body)) {
                    return rules.ArrowFunctionExpression(node);
                }
            },
            // AssignmentExpression
            // AwaitExpression
            BinaryExpression: binaryExp,
            CallExpression: callExp,
            // ClassDeclaration
            // ClassExpression
            ConditionalExpression(node) {
                // reduces the precedence of the node so the rule thinks it needs to be wrapped
                if (util.isTypeAssertion(node.test)) {
                    return rules.ConditionalExpression(Object.assign(Object.assign({}, node), { test: Object.assign(Object.assign({}, node.test), { type: experimental_utils_1.AST_NODE_TYPES.SequenceExpression }) }));
                }
                if (util.isTypeAssertion(node.consequent)) {
                    return rules.ConditionalExpression(Object.assign(Object.assign({}, node), { consequent: Object.assign(Object.assign({}, node.consequent), { type: experimental_utils_1.AST_NODE_TYPES.SequenceExpression }) }));
                }
                if (util.isTypeAssertion(node.alternate)) {
                    // reduces the precedence of the node so the rule thinks it needs to be rapped
                    return rules.ConditionalExpression(Object.assign(Object.assign({}, node), { alternate: Object.assign(Object.assign({}, node.alternate), { type: experimental_utils_1.AST_NODE_TYPES.SequenceExpression }) }));
                }
                return rules.ConditionalExpression(node);
            },
            // DoWhileStatement
            'ForInStatement, ForOfStatement'(node) {
                if (util.isTypeAssertion(node.right)) {
                    // makes the rule skip checking of the right
                    return rules['ForInStatement, ForOfStatement'](Object.assign(Object.assign({}, node), { type: experimental_utils_1.AST_NODE_TYPES.ForOfStatement, right: Object.assign(Object.assign({}, node.right), { type: experimental_utils_1.AST_NODE_TYPES.SequenceExpression }) }));
                }
                return rules['ForInStatement, ForOfStatement'](node);
            },
            ForStatement(node) {
                // make the rule skip the piece by removing it entirely
                if (node.init && util.isTypeAssertion(node.init)) {
                    return rules.ForStatement(Object.assign(Object.assign({}, node), { init: null }));
                }
                if (node.test && util.isTypeAssertion(node.test)) {
                    return rules.ForStatement(Object.assign(Object.assign({}, node), { test: null }));
                }
                if (node.update && util.isTypeAssertion(node.update)) {
                    return rules.ForStatement(Object.assign(Object.assign({}, node), { update: null }));
                }
                return rules.ForStatement(node);
            },
            'ForStatement > *.init:exit'(node) {
                if (!util.isTypeAssertion(node)) {
                    return rules['ForStatement > *.init:exit'](node);
                }
            },
            // IfStatement
            LogicalExpression: binaryExp,
            MemberExpression(node) {
                if (util.isTypeAssertion(node.object)) {
                    // reduces the precedence of the node so the rule thinks it needs to be wrapped
                    return rules.MemberExpression(Object.assign(Object.assign({}, node), { object: Object.assign(Object.assign({}, node.object), { type: experimental_utils_1.AST_NODE_TYPES.SequenceExpression }) }));
                }
                return rules.MemberExpression(node);
            },
            NewExpression: callExp,
            // ObjectExpression
            // ReturnStatement
            // SequenceExpression
            SpreadElement(node) {
                if (!util.isTypeAssertion(node.argument)) {
                    return rules.SpreadElement(node);
                }
            },
            SwitchCase(node) {
                if (node.test && !util.isTypeAssertion(node.test)) {
                    return rules.SwitchCase(node);
                }
            },
            // SwitchStatement
            ThrowStatement(node) {
                if (node.argument && !util.isTypeAssertion(node.argument)) {
                    return rules.ThrowStatement(node);
                }
            },
            UnaryExpression: unaryUpdateExpression,
            UpdateExpression: unaryUpdateExpression,
            // VariableDeclarator
            // WhileStatement
            // WithStatement - i'm not going to even bother implementing this terrible and never used feature
            YieldExpression(node) {
                if (node.argument && !util.isTypeAssertion(node.argument)) {
                    return rules.YieldExpression(node);
                }
            },
        };
        return Object.assign({}, rules, overrides);
    },
});
//# sourceMappingURL=no-extra-parens.js.map