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
const regexpp_1 = require("regexpp");
const ts = __importStar(require("typescript"));
const util_1 = require("../util");
exports.default = util_1.createRule({
    name: 'prefer-includes',
    defaultOptions: [],
    meta: {
        type: 'suggestion',
        docs: {
            description: 'Enforce `includes` method over `indexOf` method',
            category: 'Best Practices',
            recommended: 'error',
            requiresTypeChecking: true,
        },
        fixable: 'code',
        messages: {
            preferIncludes: "Use 'includes()' method instead.",
            preferStringIncludes: 'Use `String#includes()` method with a string instead.',
        },
        schema: [],
    },
    create(context) {
        const globalScope = context.getScope();
        const services = util_1.getParserServices(context);
        const types = services.program.getTypeChecker();
        function isNumber(node, value) {
            const evaluated = util_1.getStaticValue(node, globalScope);
            return evaluated !== null && evaluated.value === value;
        }
        function isPositiveCheck(node) {
            switch (node.operator) {
                case '!==':
                case '!=':
                case '>':
                    return isNumber(node.right, -1);
                case '>=':
                    return isNumber(node.right, 0);
                default:
                    return false;
            }
        }
        function isNegativeCheck(node) {
            switch (node.operator) {
                case '===':
                case '==':
                case '<=':
                    return isNumber(node.right, -1);
                case '<':
                    return isNumber(node.right, 0);
                default:
                    return false;
            }
        }
        function hasSameParameters(nodeA, nodeB) {
            if (!ts.isFunctionLike(nodeA) || !ts.isFunctionLike(nodeB)) {
                return false;
            }
            const paramsA = nodeA.parameters;
            const paramsB = nodeB.parameters;
            if (paramsA.length !== paramsB.length) {
                return false;
            }
            for (let i = 0; i < paramsA.length; ++i) {
                const paramA = paramsA[i];
                const paramB = paramsB[i];
                // Check name, type, and question token once.
                if (paramA.getText() !== paramB.getText()) {
                    return false;
                }
            }
            return true;
        }
        /**
         * Parse a given node if it's a `RegExp` instance.
         * @param node The node to parse.
         */
        function parseRegExp(node) {
            const evaluated = util_1.getStaticValue(node, globalScope);
            if (evaluated == null || !(evaluated.value instanceof RegExp)) {
                return null;
            }
            const { pattern, flags } = regexpp_1.parseRegExpLiteral(evaluated.value);
            if (pattern.alternatives.length !== 1 ||
                flags.ignoreCase ||
                flags.global) {
                return null;
            }
            // Check if it can determine a unique string.
            const chars = pattern.alternatives[0].elements;
            if (!chars.every(c => c.type === 'Character')) {
                return null;
            }
            // To string.
            return String.fromCodePoint(...chars.map(c => c.value));
        }
        return {
            "BinaryExpression > :matches(CallExpression, OptionalCallExpression).left > :matches(MemberExpression, OptionalMemberExpression).callee[property.name='indexOf'][computed=false]"(node) {
                var _a, _b;
                // Check if the comparison is equivalent to `includes()`.
                const callNode = node.parent;
                const compareNode = callNode.parent;
                const negative = isNegativeCheck(compareNode);
                if (!negative && !isPositiveCheck(compareNode)) {
                    return;
                }
                // Get the symbol of `indexOf` method.
                const tsNode = services.esTreeNodeToTSNodeMap.get(node.property);
                const indexofMethodDeclarations = (_a = types
                    .getSymbolAtLocation(tsNode)) === null || _a === void 0 ? void 0 : _a.getDeclarations();
                if (indexofMethodDeclarations == null ||
                    indexofMethodDeclarations.length === 0) {
                    return;
                }
                // Check if every declaration of `indexOf` method has `includes` method
                // and the two methods have the same parameters.
                for (const instanceofMethodDecl of indexofMethodDeclarations) {
                    const typeDecl = instanceofMethodDecl.parent;
                    const type = types.getTypeAtLocation(typeDecl);
                    const includesMethodDecl = (_b = type
                        .getProperty('includes')) === null || _b === void 0 ? void 0 : _b.getDeclarations();
                    if (includesMethodDecl == null ||
                        !includesMethodDecl.some(includesMethodDecl => hasSameParameters(includesMethodDecl, instanceofMethodDecl))) {
                        return;
                    }
                }
                // Report it.
                context.report({
                    node: compareNode,
                    messageId: 'preferIncludes',
                    *fix(fixer) {
                        if (negative) {
                            yield fixer.insertTextBefore(callNode, '!');
                        }
                        yield fixer.replaceText(node.property, 'includes');
                        yield fixer.removeRange([callNode.range[1], compareNode.range[1]]);
                    },
                });
            },
            // /bar/.test(foo)
            ':matches(CallExpression, OptionalCallExpression) > :matches(MemberExpression, OptionalMemberExpression).callee[property.name="test"][computed=false]'(node) {
                const callNode = node.parent;
                const text = callNode.arguments.length === 1 ? parseRegExp(node.object) : null;
                if (text == null) {
                    return;
                }
                context.report({
                    node: callNode,
                    messageId: 'preferStringIncludes',
                    *fix(fixer) {
                        const argNode = callNode.arguments[0];
                        const needsParen = argNode.type !== experimental_utils_1.AST_NODE_TYPES.Literal &&
                            argNode.type !== experimental_utils_1.AST_NODE_TYPES.TemplateLiteral &&
                            argNode.type !== experimental_utils_1.AST_NODE_TYPES.Identifier &&
                            argNode.type !== experimental_utils_1.AST_NODE_TYPES.MemberExpression &&
                            argNode.type !== experimental_utils_1.AST_NODE_TYPES.OptionalMemberExpression &&
                            argNode.type !== experimental_utils_1.AST_NODE_TYPES.CallExpression &&
                            argNode.type !== experimental_utils_1.AST_NODE_TYPES.OptionalCallExpression;
                        yield fixer.removeRange([callNode.range[0], argNode.range[0]]);
                        if (needsParen) {
                            yield fixer.insertTextBefore(argNode, '(');
                            yield fixer.insertTextAfter(argNode, ')');
                        }
                        yield fixer.insertTextAfter(argNode, `${callNode.type === experimental_utils_1.AST_NODE_TYPES.OptionalCallExpression
                            ? '?.'
                            : '.'}includes(${JSON.stringify(text)}`);
                    },
                });
            },
        };
    },
});
//# sourceMappingURL=prefer-includes.js.map