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
function removeSpaces(str) {
    return str.replace(/ /g, '');
}
function stringifyTypeName(node, sourceCode) {
    return removeSpaces(sourceCode.getText(node));
}
function getCustomMessage(bannedType) {
    if (bannedType === null) {
        return '';
    }
    if (typeof bannedType === 'string') {
        return ` ${bannedType}`;
    }
    if (bannedType.message) {
        return ` ${bannedType.message}`;
    }
    return '';
}
/*
  Defaults for this rule should be treated as an "all or nothing"
  merge, so we need special handling here.

  See: https://github.com/typescript-eslint/typescript-eslint/issues/686
 */
const defaultTypes = {
    String: {
        message: 'Use string instead',
        fixWith: 'string',
    },
    Boolean: {
        message: 'Use boolean instead',
        fixWith: 'boolean',
    },
    Number: {
        message: 'Use number instead',
        fixWith: 'number',
    },
    Object: {
        message: 'Use Record<string, any> instead',
        fixWith: 'Record<string, any>',
    },
    Symbol: {
        message: 'Use symbol instead',
        fixWith: 'symbol',
    },
};
exports.default = util.createRule({
    name: 'ban-types',
    meta: {
        type: 'suggestion',
        docs: {
            description: 'Bans specific types from being used',
            category: 'Best Practices',
            recommended: 'error',
        },
        fixable: 'code',
        messages: {
            bannedTypeMessage: "Don't use '{{name}}' as a type.{{customMessage}}",
        },
        schema: [
            {
                type: 'object',
                properties: {
                    types: {
                        type: 'object',
                        additionalProperties: {
                            oneOf: [
                                { type: 'null' },
                                { type: 'string' },
                                {
                                    type: 'object',
                                    properties: {
                                        message: { type: 'string' },
                                        fixWith: { type: 'string' },
                                    },
                                    additionalProperties: false,
                                },
                            ],
                        },
                    },
                    extendDefaults: {
                        type: 'boolean',
                    },
                },
                additionalProperties: false,
            },
        ],
    },
    defaultOptions: [{}],
    create(context, [options]) {
        var _a, _b;
        const extendDefaults = (_a = options.extendDefaults) !== null && _a !== void 0 ? _a : true;
        const customTypes = (_b = options.types) !== null && _b !== void 0 ? _b : {};
        const types = Object.assign(Object.assign({}, (extendDefaults ? defaultTypes : {})), customTypes);
        const bannedTypes = new Map(Object.entries(types).map(([type, data]) => [removeSpaces(type), data]));
        function checkBannedTypes(typeNode, name = stringifyTypeName(typeNode, context.getSourceCode())) {
            const bannedType = bannedTypes.get(name);
            if (bannedType !== undefined) {
                const customMessage = getCustomMessage(bannedType);
                const fixWith = bannedType && typeof bannedType === 'object' && bannedType.fixWith;
                context.report({
                    node: typeNode,
                    messageId: 'bannedTypeMessage',
                    data: {
                        name,
                        customMessage,
                    },
                    fix: fixWith
                        ? (fixer) => fixer.replaceText(typeNode, fixWith)
                        : null,
                });
            }
        }
        return Object.assign(Object.assign(Object.assign({}, (bannedTypes.has('null') && {
            TSNullKeyword(node) {
                checkBannedTypes(node, 'null');
            },
        })), (bannedTypes.has('undefined') && {
            TSUndefinedKeyword(node) {
                checkBannedTypes(node, 'undefined');
            },
        })), { TSTypeLiteral(node) {
                if (node.members.length) {
                    return;
                }
                checkBannedTypes(node);
            },
            TSTypeReference({ typeName }) {
                checkBannedTypes(typeName);
            } });
    },
});
//# sourceMappingURL=ban-types.js.map