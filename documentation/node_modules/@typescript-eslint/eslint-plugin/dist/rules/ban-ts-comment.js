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
const defaultOptions = [
    {
        'ts-expect-error': true,
        'ts-ignore': true,
        'ts-nocheck': true,
        'ts-check': false,
    },
];
exports.default = util.createRule({
    name: 'ban-ts-comment',
    meta: {
        type: 'problem',
        docs: {
            description: 'Bans `// @ts-<directive>` comments from being used',
            category: 'Best Practices',
            recommended: false,
        },
        messages: {
            tsDirectiveComment: 'Do not use "// @ts-{{directive}}" because it alters compilation errors.',
        },
        schema: [
            {
                type: 'object',
                properties: {
                    'ts-expect-error': {
                        type: 'boolean',
                        default: true,
                    },
                    'ts-ignore': {
                        type: 'boolean',
                        default: true,
                    },
                    'ts-nocheck': {
                        type: 'boolean',
                        default: true,
                    },
                    'ts-check': {
                        type: 'boolean',
                        default: false,
                    },
                },
                additionalProperties: false,
            },
        ],
    },
    defaultOptions,
    create(context, [options]) {
        const tsCommentRegExp = /^\/*\s*@ts-(expect-error|ignore|check|nocheck)/;
        const sourceCode = context.getSourceCode();
        return {
            Program() {
                const comments = sourceCode.getAllComments();
                comments.forEach(comment => {
                    var _a;
                    if (comment.type !== experimental_utils_1.AST_TOKEN_TYPES.Line) {
                        return;
                    }
                    const [, directive] = (_a = tsCommentRegExp.exec(comment.value)) !== null && _a !== void 0 ? _a : [];
                    const fullDirective = `ts-${directive}`;
                    if (options[fullDirective]) {
                        context.report({
                            data: { directive },
                            node: comment,
                            messageId: 'tsDirectiveComment',
                        });
                    }
                });
            },
        };
    },
});
//# sourceMappingURL=ban-ts-comment.js.map