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
const tsutils = __importStar(require("tsutils"));
const ts = __importStar(require("typescript"));
const util = __importStar(require("../util"));
exports.default = util.createRule({
    name: 'no-unnecessary-boolean-literal-compare',
    meta: {
        docs: {
            description: 'Flags unnecessary equality comparisons against boolean literals',
            category: 'Stylistic Issues',
            recommended: false,
            requiresTypeChecking: true,
        },
        fixable: 'code',
        messages: {
            direct: 'This expression unnecessarily compares a boolean value to a boolean instead of using it directly.',
            negated: 'This expression unnecessarily compares a boolean value to a boolean instead of negating it.',
        },
        schema: [],
        type: 'suggestion',
    },
    defaultOptions: [],
    create(context) {
        const parserServices = util.getParserServices(context);
        const checker = parserServices.program.getTypeChecker();
        function getBooleanComparison(node) {
            const comparison = deconstructComparison(node);
            if (!comparison) {
                return undefined;
            }
            const expressionType = checker.getTypeAtLocation(parserServices.esTreeNodeToTSNodeMap.get(comparison.expression));
            if (!tsutils.isTypeFlagSet(expressionType, ts.TypeFlags.Boolean | ts.TypeFlags.BooleanLiteral)) {
                return undefined;
            }
            return comparison;
        }
        function deconstructComparison(node) {
            const comparisonType = util.getEqualsKind(node.operator);
            if (!comparisonType) {
                return undefined;
            }
            for (const [against, expression] of [
                [node.right, node.left],
                [node.left, node.right],
            ]) {
                if (against.type !== experimental_utils_1.AST_NODE_TYPES.Literal ||
                    typeof against.value !== 'boolean') {
                    continue;
                }
                const { value } = against;
                const negated = node.operator.startsWith('!');
                return {
                    forTruthy: value ? !negated : negated,
                    expression,
                    negated,
                    range: expression.range[0] < against.range[0]
                        ? [expression.range[1], against.range[1]]
                        : [against.range[1], expression.range[1]],
                };
            }
            return undefined;
        }
        return {
            BinaryExpression(node) {
                const comparison = getBooleanComparison(node);
                if (comparison) {
                    context.report({
                        fix: function* (fixer) {
                            yield fixer.removeRange(comparison.range);
                            if (!comparison.forTruthy) {
                                yield fixer.insertTextBefore(node, '!');
                            }
                        },
                        messageId: comparison.negated ? 'negated' : 'direct',
                        node,
                    });
                }
            },
        };
    },
});
//# sourceMappingURL=no-unnecessary-boolean-literal-compare.js.map