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
const camelcase_1 = __importDefault(require("eslint/lib/rules/camelcase"));
const util = __importStar(require("../util"));
const schema = util.deepMerge(Array.isArray(camelcase_1.default.meta.schema)
    ? camelcase_1.default.meta.schema[0]
    : camelcase_1.default.meta.schema, {
    properties: {
        genericType: {
            enum: ['always', 'never'],
        },
    },
});
exports.default = util.createRule({
    name: 'camelcase',
    meta: {
        type: 'suggestion',
        docs: {
            description: 'Enforce camelCase naming convention',
            category: 'Stylistic Issues',
            recommended: 'error',
            extendsBaseRule: true,
        },
        deprecated: true,
        replacedBy: ['naming-convention'],
        schema: [schema],
        messages: camelcase_1.default.meta.messages,
    },
    defaultOptions: [
        {
            allow: ['^UNSAFE_'],
            ignoreDestructuring: false,
            properties: 'never',
            genericType: 'never',
        },
    ],
    create(context, [options]) {
        var _a, _b;
        const rules = camelcase_1.default.create(context);
        const TS_PROPERTY_TYPES = [
            experimental_utils_1.AST_NODE_TYPES.TSPropertySignature,
            experimental_utils_1.AST_NODE_TYPES.ClassProperty,
            experimental_utils_1.AST_NODE_TYPES.TSParameterProperty,
            experimental_utils_1.AST_NODE_TYPES.TSAbstractClassProperty,
        ];
        const genericType = options.genericType;
        const properties = options.properties;
        const allow = (_b = (_a = options.allow) === null || _a === void 0 ? void 0 : _a.map(entry => ({
            name: entry,
            regex: new RegExp(entry),
        }))) !== null && _b !== void 0 ? _b : [];
        /**
         * Checks if a string contains an underscore and isn't all upper-case
         * @param  name The string to check.
         */
        function isUnderscored(name) {
            // if there's an underscore, it might be A_CONSTANT, which is okay
            return name.includes('_') && name !== name.toUpperCase();
        }
        /**
         * Checks if a string match the ignore list
         * @param name The string to check.
         * @returns if the string is ignored
         * @private
         */
        function isAllowed(name) {
            return (allow.findIndex(entry => name === entry.name || entry.regex.test(name)) !== -1);
        }
        /**
         * Checks if the the node is a valid TypeScript property type.
         * @param node the node to be validated.
         * @returns true if the node is a TypeScript property type.
         * @private
         */
        function isTSPropertyType(node) {
            if (TS_PROPERTY_TYPES.includes(node.type)) {
                return true;
            }
            if (node.type === experimental_utils_1.AST_NODE_TYPES.AssignmentPattern) {
                return (node.parent !== undefined &&
                    TS_PROPERTY_TYPES.includes(node.parent.type));
            }
            return false;
        }
        function report(node) {
            context.report({
                node,
                messageId: 'notCamelCase',
                data: { name: node.name },
            });
        }
        return {
            Identifier(node) {
                /*
                 * Leading and trailing underscores are commonly used to flag
                 * private/protected identifiers, strip them
                 */
                const name = node.name.replace(/^_+|_+$/g, '');
                // First, we ignore the node if it match the ignore list
                if (isAllowed(name)) {
                    return;
                }
                // Check TypeScript specific nodes
                const parent = node.parent;
                if (parent && isTSPropertyType(parent)) {
                    if (properties === 'always' && isUnderscored(name)) {
                        report(node);
                    }
                    return;
                }
                if (parent && parent.type === experimental_utils_1.AST_NODE_TYPES.TSTypeParameter) {
                    if (genericType === 'always' && isUnderscored(name)) {
                        report(node);
                    }
                    return;
                }
                if (parent && parent.type === experimental_utils_1.AST_NODE_TYPES.OptionalMemberExpression) {
                    // Report underscored object names
                    if (properties === 'always' &&
                        parent.object.type === experimental_utils_1.AST_NODE_TYPES.Identifier &&
                        parent.object.name === node.name &&
                        isUnderscored(name)) {
                        report(node);
                    }
                    return;
                }
                // Let the base rule deal with the rest
                rules.Identifier(node);
            },
        };
    },
});
//# sourceMappingURL=camelcase.js.map