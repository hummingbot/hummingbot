"use strict";
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (Object.hasOwnProperty.call(mod, k)) result[k] = mod[k];
    result["default"] = mod;
    return result;
};
Object.defineProperty(exports, "__esModule", { value: true });
const util = __importStar(require("../util"));
/**
 * Parses a given value as options.
 */
function parseOptions([options]) {
    if (options === 'always') {
        return { prefixWithI: 'always', allowUnderscorePrefix: false };
    }
    if (options !== 'never' && options.prefixWithI === 'always') {
        return {
            prefixWithI: 'always',
            allowUnderscorePrefix: !!options.allowUnderscorePrefix,
        };
    }
    return { prefixWithI: 'never' };
}
exports.parseOptions = parseOptions;
exports.default = util.createRule({
    name: 'interface-name-prefix',
    meta: {
        type: 'suggestion',
        docs: {
            description: 'Require that interface names should or should not prefixed with `I`',
            category: 'Stylistic Issues',
            // this will always be recommended as there's no reason to use this convention
            // https://github.com/typescript-eslint/typescript-eslint/issues/374
            recommended: 'error',
        },
        deprecated: true,
        replacedBy: ['naming-convention'],
        messages: {
            noPrefix: 'Interface name must not be prefixed with "I".',
            alwaysPrefix: 'Interface name must be prefixed with "I".',
        },
        schema: [
            {
                oneOf: [
                    {
                        enum: [
                            // Deprecated, equivalent to: { prefixWithI: 'never' }
                            'never',
                            // Deprecated, equivalent to: { prefixWithI: 'always', allowUnderscorePrefix: false }
                            'always',
                        ],
                    },
                    {
                        type: 'object',
                        properties: {
                            prefixWithI: {
                                type: 'string',
                                enum: ['never'],
                            },
                        },
                        additionalProperties: false,
                    },
                    {
                        type: 'object',
                        properties: {
                            prefixWithI: {
                                type: 'string',
                                enum: ['always'],
                            },
                            allowUnderscorePrefix: {
                                type: 'boolean',
                            },
                        },
                        required: ['prefixWithI'],
                        additionalProperties: false,
                    },
                ],
            },
        ],
    },
    defaultOptions: [{ prefixWithI: 'never' }],
    create(context, [options]) {
        const parsedOptions = parseOptions([options]);
        /**
         * Checks if a string is prefixed with "I".
         * @param name The string to check
         */
        function isPrefixedWithI(name) {
            return /^I[A-Z]/.test(name);
        }
        /**
         * Checks if a string is prefixed with "I" or "_I".
         * @param name The string to check
         */
        function isPrefixedWithIOrUnderscoreI(name) {
            return /^_?I[A-Z]/.test(name);
        }
        return {
            TSInterfaceDeclaration(node) {
                if (parsedOptions.prefixWithI === 'never') {
                    if (isPrefixedWithIOrUnderscoreI(node.id.name)) {
                        context.report({
                            node: node.id,
                            messageId: 'noPrefix',
                        });
                    }
                }
                else {
                    if (parsedOptions.allowUnderscorePrefix) {
                        if (!isPrefixedWithIOrUnderscoreI(node.id.name)) {
                            context.report({
                                node: node.id,
                                messageId: 'alwaysPrefix',
                            });
                        }
                    }
                    else {
                        if (!isPrefixedWithI(node.id.name)) {
                            context.report({
                                node: node.id,
                                messageId: 'alwaysPrefix',
                            });
                        }
                    }
                }
            },
        };
    },
});
//# sourceMappingURL=interface-name-prefix.js.map