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
const ts = __importStar(require("typescript"));
const tsutils = __importStar(require("tsutils"));
const util = __importStar(require("../util"));
exports.default = util.createRule({
    name: 'strict-boolean-expressions',
    meta: {
        type: 'suggestion',
        docs: {
            description: 'Restricts the types allowed in boolean expressions',
            category: 'Best Practices',
            recommended: false,
            requiresTypeChecking: true,
        },
        schema: [
            {
                type: 'object',
                properties: {
                    ignoreRhs: {
                        type: 'boolean',
                    },
                    allowNullable: {
                        type: 'boolean',
                    },
                    allowSafe: {
                        type: 'boolean',
                    },
                },
                additionalProperties: false,
            },
        ],
        messages: {
            conditionErrorOther: 'Unexpected value in conditional. ' +
                'A boolean expression is required.',
            conditionErrorAny: 'Unexpected any value in conditional. ' +
                'An explicit comparison or type cast is required.',
            conditionErrorNullish: 'Unexpected nullish value in conditional. ' +
                'The condition is always false.',
            conditionErrorNullableBoolean: 'Unexpected nullable boolean value in conditional. ' +
                'Please handle the nullish case explicitly.',
            conditionErrorString: 'Unexpected string value in conditional. ' +
                'An explicit empty string check is required.',
            conditionErrorNullableString: 'Unexpected nullable string value in conditional. ' +
                'Please handle the nullish/empty cases explicitly.',
            conditionErrorNumber: 'Unexpected number value in conditional. ' +
                'An explicit zero/NaN check is required.',
            conditionErrorNullableNumber: 'Unexpected nullable number value in conditional. ' +
                'Please handle the nullish/zero/NaN cases explicitly.',
            conditionErrorObject: 'Unexpected object value in conditional. ' +
                'The condition is always true.',
            conditionErrorNullableObject: 'Unexpected nullable object value in conditional. ' +
                'An explicit null check is required.',
        },
    },
    defaultOptions: [
        {
            ignoreRhs: false,
            allowNullable: false,
            allowSafe: false,
        },
    ],
    create(context, [options]) {
        const service = util.getParserServices(context);
        const checker = service.program.getTypeChecker();
        const checkedNodes = new Set();
        return {
            ConditionalExpression: checkTestExpression,
            DoWhileStatement: checkTestExpression,
            ForStatement: checkTestExpression,
            IfStatement: checkTestExpression,
            WhileStatement: checkTestExpression,
            'LogicalExpression[operator!="??"]': checkNode,
            'UnaryExpression[operator="!"]': checkUnaryLogicalExpression,
        };
        function checkTestExpression(node) {
            if (node.test == null) {
                return;
            }
            checkNode(node.test, true);
        }
        function checkUnaryLogicalExpression(node) {
            checkNode(node.argument, true);
        }
        /**
         * This function analyzes the type of a boolean expression node and checks if it is allowed.
         * It can recurse when checking nested logical operators, so that only the outermost expressions are reported.
         * @param node The AST node to check.
         * @param isRoot Whether it is the root of a logical expression and there was no recursion yet.
         * @returns `true` if there was an error reported.
         */
        function checkNode(node, isRoot = false) {
            // prevent checking the same node multiple times
            if (checkedNodes.has(node)) {
                return false;
            }
            checkedNodes.add(node);
            // for logical operator, we also check its operands
            if (node.type === experimental_utils_1.AST_NODE_TYPES.LogicalExpression &&
                node.operator !== '??') {
                let hasError = false;
                if (checkNode(node.left)) {
                    hasError = true;
                }
                if (!options.ignoreRhs) {
                    if (checkNode(node.right)) {
                        hasError = true;
                    }
                }
                // if this logical operator is not the root of a logical expression
                // we only check its operands and return
                if (!isRoot) {
                    return hasError;
                }
                // if this is the root of a logical expression
                // we want to check its resulting type too
                else {
                    // ...unless there already was an error, we exit so we don't double-report
                    if (hasError) {
                        return true;
                    }
                }
            }
            const tsNode = service.esTreeNodeToTSNodeMap.get(node);
            const type = util.getConstrainedTypeAtLocation(checker, tsNode);
            let messageId;
            const types = inspectVariantTypes(tsutils.unionTypeParts(type));
            const is = (...wantedTypes) => types.size === wantedTypes.length &&
                wantedTypes.every(type => types.has(type));
            // boolean
            if (is('boolean')) {
                // boolean is always okay
                return false;
            }
            // never
            if (is('never')) {
                // never is always okay
                return false;
            }
            // nullish
            else if (is('nullish')) {
                // condition is always false
                messageId = 'conditionErrorNullish';
            }
            // nullable boolean
            else if (is('nullish', 'boolean')) {
                if (!options.allowNullable) {
                    messageId = 'conditionErrorNullableBoolean';
                }
            }
            // string
            else if (is('string')) {
                messageId = 'conditionErrorString';
            }
            // nullable string
            else if (is('nullish', 'string')) {
                messageId = 'conditionErrorNullableString';
            }
            // number
            else if (is('number')) {
                messageId = 'conditionErrorNumber';
            }
            // nullable number
            else if (is('nullish', 'number')) {
                messageId = 'conditionErrorNullableNumber';
            }
            // object
            else if (is('object')) {
                // condition is always true
                if (!options.allowSafe) {
                    messageId = 'conditionErrorObject';
                }
            }
            // nullable object
            else if (is('nullish', 'object')) {
                if (!options.allowSafe || !options.allowNullable) {
                    messageId = 'conditionErrorNullableObject';
                }
            }
            // boolean/object
            else if (is('boolean', 'object')) {
                if (!options.allowSafe) {
                    messageId = 'conditionErrorOther';
                }
            }
            // nullable boolean/object
            else if (is('nullish', 'boolean', 'object')) {
                if (!options.allowSafe || !options.allowNullable) {
                    messageId = 'conditionErrorOther';
                }
            }
            // any
            else if (is('any')) {
                messageId = 'conditionErrorAny';
            }
            // other
            else {
                messageId = 'conditionErrorOther';
            }
            if (messageId != null) {
                context.report({ node, messageId });
                return true;
            }
            return false;
        }
        /**
         * Check union variants for the types we care about
         */
        function inspectVariantTypes(types) {
            const variantTypes = new Set();
            if (types.some(type => tsutils.isTypeFlagSet(type, ts.TypeFlags.Null | ts.TypeFlags.Undefined | ts.TypeFlags.VoidLike))) {
                variantTypes.add('nullish');
            }
            if (types.some(type => tsutils.isTypeFlagSet(type, ts.TypeFlags.BooleanLike))) {
                variantTypes.add('boolean');
            }
            if (types.some(type => tsutils.isTypeFlagSet(type, ts.TypeFlags.StringLike))) {
                variantTypes.add('string');
            }
            if (types.some(type => tsutils.isTypeFlagSet(type, ts.TypeFlags.NumberLike))) {
                variantTypes.add('number');
            }
            if (types.some(type => !tsutils.isTypeFlagSet(type, ts.TypeFlags.Null |
                ts.TypeFlags.Undefined |
                ts.TypeFlags.VoidLike |
                ts.TypeFlags.BooleanLike |
                ts.TypeFlags.StringLike |
                ts.TypeFlags.NumberLike |
                ts.TypeFlags.Any |
                ts.TypeFlags.Unknown |
                ts.TypeFlags.Never))) {
                variantTypes.add('object');
            }
            if (types.some(type => tsutils.isTypeFlagSet(type, ts.TypeFlags.Any | ts.TypeFlags.Unknown))) {
                variantTypes.add('any');
            }
            if (types.some(type => tsutils.isTypeFlagSet(type, ts.TypeFlags.Never))) {
                variantTypes.add('never');
            }
            return variantTypes;
        }
    },
});
//# sourceMappingURL=strict-boolean-expressions.js.map