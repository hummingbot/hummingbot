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
const no_dupe_class_members_1 = __importDefault(require("eslint/lib/rules/no-dupe-class-members"));
const util = __importStar(require("../util"));
exports.default = util.createRule({
    name: 'no-dupe-class-members',
    meta: {
        type: 'problem',
        docs: {
            description: 'Disallow duplicate class members',
            category: 'Possible Errors',
            recommended: false,
            extendsBaseRule: true,
        },
        schema: no_dupe_class_members_1.default.meta.schema,
        messages: no_dupe_class_members_1.default.meta.messages,
    },
    defaultOptions: [],
    create(context) {
        const rules = no_dupe_class_members_1.default.create(context);
        return Object.assign(Object.assign({}, rules), { MethodDefinition(node) {
                if (node.computed) {
                    return;
                }
                if (node.value.type === experimental_utils_1.AST_NODE_TYPES.TSEmptyBodyFunctionExpression) {
                    return;
                }
                return rules.MethodDefinition(node);
            } });
    },
});
//# sourceMappingURL=no-dupe-class-members.js.map