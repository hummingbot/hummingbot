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
const util = __importStar(require("../util"));
const experimental_utils_1 = require("@typescript-eslint/experimental-utils");
exports.default = util.createRule({
    name: 'no-throw-literal',
    meta: {
        type: 'problem',
        docs: {
            description: 'Disallow throwing literals as exceptions',
            category: 'Best Practices',
            recommended: false,
            requiresTypeChecking: true,
        },
        schema: [],
        messages: {
            object: 'Expected an error object to be thrown.',
            undef: 'Do not throw undefined.',
        },
    },
    defaultOptions: [],
    create(context) {
        const parserServices = util.getParserServices(context);
        const program = parserServices.program;
        const checker = program.getTypeChecker();
        function isErrorLike(type) {
            var _a;
            const symbol = type.getSymbol();
            if (!symbol) {
                return false;
            }
            if (symbol.getName() === 'Error') {
                const declarations = (_a = symbol.getDeclarations()) !== null && _a !== void 0 ? _a : [];
                for (const declaration of declarations) {
                    const sourceFile = declaration.getSourceFile();
                    if (program.isSourceFileDefaultLibrary(sourceFile)) {
                        return true;
                    }
                }
            }
            if (symbol.flags & (ts.SymbolFlags.Class | ts.SymbolFlags.Interface)) {
                for (const baseType of checker.getBaseTypes(type)) {
                    if (isErrorLike(baseType)) {
                        return true;
                    }
                }
            }
            return false;
        }
        function tryGetThrowArgumentType(node) {
            switch (node.type) {
                case experimental_utils_1.AST_NODE_TYPES.Identifier:
                case experimental_utils_1.AST_NODE_TYPES.CallExpression:
                case experimental_utils_1.AST_NODE_TYPES.NewExpression:
                case experimental_utils_1.AST_NODE_TYPES.MemberExpression: {
                    const tsNode = parserServices.esTreeNodeToTSNodeMap.get(node);
                    return checker.getTypeAtLocation(tsNode);
                }
                case experimental_utils_1.AST_NODE_TYPES.AssignmentExpression:
                    return tryGetThrowArgumentType(node.right);
                case experimental_utils_1.AST_NODE_TYPES.SequenceExpression:
                    return tryGetThrowArgumentType(node.expressions[node.expressions.length - 1]);
                case experimental_utils_1.AST_NODE_TYPES.LogicalExpression: {
                    const left = tryGetThrowArgumentType(node.left);
                    return left !== null && left !== void 0 ? left : tryGetThrowArgumentType(node.right);
                }
                case experimental_utils_1.AST_NODE_TYPES.ConditionalExpression: {
                    const consequent = tryGetThrowArgumentType(node.consequent);
                    return consequent !== null && consequent !== void 0 ? consequent : tryGetThrowArgumentType(node.alternate);
                }
                default:
                    return null;
            }
        }
        function checkThrowArgument(node) {
            if (node.type === experimental_utils_1.AST_NODE_TYPES.AwaitExpression ||
                node.type === experimental_utils_1.AST_NODE_TYPES.YieldExpression) {
                return;
            }
            const type = tryGetThrowArgumentType(node);
            if (type) {
                if (type.flags & ts.TypeFlags.Undefined) {
                    context.report({ node, messageId: 'undef' });
                    return;
                }
                if (type.flags & (ts.TypeFlags.Any | ts.TypeFlags.Unknown) ||
                    isErrorLike(type)) {
                    return;
                }
            }
            context.report({ node, messageId: 'object' });
        }
        return {
            ThrowStatement(node) {
                if (node.argument) {
                    checkThrowArgument(node.argument);
                }
            },
        };
    },
});
//# sourceMappingURL=no-throw-literal.js.map