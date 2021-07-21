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
const lines_between_class_members_1 = __importDefault(require("eslint/lib/rules/lines-between-class-members"));
const util = __importStar(require("../util"));
const schema = util.deepMerge(Object.assign({}, lines_between_class_members_1.default.meta.schema), {
    1: {
        exceptAfterOverload: {
            type: 'booleean',
            default: true,
        },
    },
});
exports.default = util.createRule({
    name: 'lines-between-class-members',
    meta: {
        type: 'layout',
        docs: {
            description: 'Require or disallow an empty line between class members',
            category: 'Stylistic Issues',
            recommended: false,
            extendsBaseRule: true,
        },
        fixable: 'whitespace',
        schema,
        messages: lines_between_class_members_1.default.meta.messages,
    },
    defaultOptions: [
        'always',
        {
            exceptAfterOverload: true,
            exceptAfterSingleLine: false,
        },
    ],
    create(context, options) {
        var _a;
        const rules = lines_between_class_members_1.default.create(context);
        const exceptAfterOverload = ((_a = options[1]) === null || _a === void 0 ? void 0 : _a.exceptAfterOverload) && options[0] === 'always';
        function isOverload(node) {
            return (node.type === experimental_utils_1.AST_NODE_TYPES.MethodDefinition &&
                node.value.type === experimental_utils_1.AST_NODE_TYPES.TSEmptyBodyFunctionExpression);
        }
        return {
            ClassBody(node) {
                const body = exceptAfterOverload
                    ? node.body.filter(node => !isOverload(node))
                    : node.body;
                rules.ClassBody(Object.assign(Object.assign({}, node), { body }));
            },
        };
    },
});
//# sourceMappingURL=lines-between-class-members.js.map