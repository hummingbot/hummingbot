"use strict";
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (Object.hasOwnProperty.call(mod, k)) result[k] = mod[k];
    result["default"] = mod;
    return result;
};
Object.defineProperty(exports, "__esModule", { value: true });
const ts = __importStar(require("typescript"));
const experimental_utils_1 = require("@typescript-eslint/experimental-utils");
const tsutils = __importStar(require("tsutils"));
const util = __importStar(require("../util"));
const FUNCTION_CONSTRUCTOR = 'Function';
const EVAL_LIKE_METHODS = new Set([
    'setImmediate',
    'setInterval',
    'setTimeout',
    'execScript',
]);
exports.default = util.createRule({
    name: 'no-implied-eval',
    meta: {
        docs: {
            description: 'Disallow the use of `eval()`-like methods',
            category: 'Best Practices',
            recommended: false,
            requiresTypeChecking: true,
        },
        messages: {
            noImpliedEvalError: 'Implied eval. Consider passing a function.',
            noFunctionConstructor: 'Implied eval. Do not use the Function constructor to create functions.',
        },
        schema: [],
        type: 'suggestion',
    },
    defaultOptions: [],
    create(context) {
        const parserServices = util.getParserServices(context);
        const checker = parserServices.program.getTypeChecker();
        function getCalleeName(node) {
            if (node.type === experimental_utils_1.AST_NODE_TYPES.Identifier) {
                return node.name;
            }
            if (node.type === experimental_utils_1.AST_NODE_TYPES.MemberExpression &&
                node.object.type === experimental_utils_1.AST_NODE_TYPES.Identifier &&
                node.object.name === 'window') {
                if (node.property.type === experimental_utils_1.AST_NODE_TYPES.Identifier) {
                    return node.property.name;
                }
                if (node.property.type === experimental_utils_1.AST_NODE_TYPES.Literal &&
                    typeof node.property.value === 'string') {
                    return node.property.value;
                }
            }
            return null;
        }
        function isFunctionType(node) {
            const tsNode = parserServices.esTreeNodeToTSNodeMap.get(node);
            const type = checker.getTypeAtLocation(tsNode);
            const symbol = type.getSymbol();
            if (symbol &&
                tsutils.isSymbolFlagSet(symbol, ts.SymbolFlags.Function | ts.SymbolFlags.Method)) {
                return true;
            }
            const signatures = checker.getSignaturesOfType(type, ts.SignatureKind.Call);
            return signatures.length > 0;
        }
        function isFunction(node) {
            switch (node.type) {
                case experimental_utils_1.AST_NODE_TYPES.ArrowFunctionExpression:
                case experimental_utils_1.AST_NODE_TYPES.FunctionDeclaration:
                case experimental_utils_1.AST_NODE_TYPES.FunctionExpression:
                    return true;
                case experimental_utils_1.AST_NODE_TYPES.MemberExpression:
                case experimental_utils_1.AST_NODE_TYPES.Identifier:
                    return isFunctionType(node);
                case experimental_utils_1.AST_NODE_TYPES.CallExpression:
                    return ((node.callee.type === experimental_utils_1.AST_NODE_TYPES.Identifier &&
                        node.callee.name === 'bind') ||
                        isFunctionType(node));
                default:
                    return false;
            }
        }
        function checkImpliedEval(node) {
            const calleeName = getCalleeName(node.callee);
            if (calleeName === null) {
                return;
            }
            if (calleeName === FUNCTION_CONSTRUCTOR) {
                context.report({ node, messageId: 'noFunctionConstructor' });
                return;
            }
            if (node.arguments.length === 0) {
                return;
            }
            const [handler] = node.arguments;
            if (EVAL_LIKE_METHODS.has(calleeName) && !isFunction(handler)) {
                context.report({ node: handler, messageId: 'noImpliedEvalError' });
            }
        }
        return {
            NewExpression: checkImpliedEval,
            CallExpression: checkImpliedEval,
        };
    },
});
//# sourceMappingURL=no-implied-eval.js.map