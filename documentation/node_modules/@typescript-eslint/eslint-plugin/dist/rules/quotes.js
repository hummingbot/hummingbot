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
const quotes_1 = __importDefault(require("eslint/lib/rules/quotes"));
const util = __importStar(require("../util"));
exports.default = util.createRule({
    name: 'quotes',
    meta: {
        type: 'layout',
        docs: {
            description: 'Enforce the consistent use of either backticks, double, or single quotes',
            category: 'Stylistic Issues',
            recommended: false,
            extendsBaseRule: true,
        },
        fixable: 'code',
        messages: quotes_1.default.meta.messages,
        schema: quotes_1.default.meta.schema,
    },
    defaultOptions: [
        'double',
        {
            allowTemplateLiterals: false,
            avoidEscape: false,
        },
    ],
    create(context, [option]) {
        const rules = quotes_1.default.create(context);
        function isAllowedAsNonBacktick(node) {
            const parent = node.parent;
            switch (parent === null || parent === void 0 ? void 0 : parent.type) {
                case experimental_utils_1.AST_NODE_TYPES.TSAbstractMethodDefinition:
                case experimental_utils_1.AST_NODE_TYPES.TSMethodSignature:
                case experimental_utils_1.AST_NODE_TYPES.TSPropertySignature:
                case experimental_utils_1.AST_NODE_TYPES.TSModuleDeclaration:
                case experimental_utils_1.AST_NODE_TYPES.TSLiteralType:
                case experimental_utils_1.AST_NODE_TYPES.TSExternalModuleReference:
                    return true;
                case experimental_utils_1.AST_NODE_TYPES.TSEnumMember:
                    return node === parent.id;
                case experimental_utils_1.AST_NODE_TYPES.TSAbstractClassProperty:
                case experimental_utils_1.AST_NODE_TYPES.ClassProperty:
                    return node === parent.key;
                default:
                    return false;
            }
        }
        return {
            Literal(node) {
                if (option === 'backtick' && isAllowedAsNonBacktick(node)) {
                    return;
                }
                rules.Literal(node);
            },
            TemplateLiteral(node) {
                rules.TemplateLiteral(node);
            },
        };
    },
});
//# sourceMappingURL=quotes.js.map