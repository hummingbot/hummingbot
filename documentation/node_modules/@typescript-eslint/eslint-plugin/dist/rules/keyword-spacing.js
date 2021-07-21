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
const keyword_spacing_1 = __importDefault(require("eslint/lib/rules/keyword-spacing"));
const util = __importStar(require("../util"));
exports.default = util.createRule({
    name: 'keyword-spacing',
    meta: {
        type: 'layout',
        docs: {
            description: 'Enforce consistent spacing before and after keywords',
            category: 'Stylistic Issues',
            recommended: false,
            extendsBaseRule: true,
        },
        fixable: 'whitespace',
        schema: keyword_spacing_1.default.meta.schema,
        messages: keyword_spacing_1.default.meta.messages,
    },
    defaultOptions: [{}],
    create(context) {
        const sourceCode = context.getSourceCode();
        const baseRules = keyword_spacing_1.default.create(context);
        return Object.assign(Object.assign({}, baseRules), { TSAsExpression(node) {
                const asToken = util.nullThrows(sourceCode.getTokenAfter(node.expression, token => token.value === 'as'), util.NullThrowsReasons.MissingToken('as', node.type));
                const oldTokenType = asToken.type;
                // as is a contextual keyword, so it's always reported as an Identifier
                // the rule looks for keyword tokens, so we temporarily override it
                // we mutate it at the token level because the rule calls sourceCode.getFirstToken,
                // so mutating a copy would not change the underlying copy returned by that method
                asToken.type = experimental_utils_1.AST_TOKEN_TYPES.Keyword;
                // use this selector just because it is just a call to `checkSpacingAroundFirstToken`
                baseRules.DebuggerStatement(asToken);
                // make sure to reset the type afterward so we don't permanently mutate the AST
                asToken.type = oldTokenType;
            } });
    },
});
//# sourceMappingURL=keyword-spacing.js.map