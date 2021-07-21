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
const no_extra_semi_1 = __importDefault(require("eslint/lib/rules/no-extra-semi"));
const util = __importStar(require("../util"));
exports.default = util.createRule({
    name: 'no-extra-semi',
    meta: {
        type: 'suggestion',
        docs: {
            description: 'Disallow unnecessary semicolons',
            category: 'Possible Errors',
            recommended: false,
            extendsBaseRule: true,
        },
        fixable: 'code',
        schema: no_extra_semi_1.default.meta.schema,
        messages: no_extra_semi_1.default.meta.messages,
    },
    defaultOptions: [],
    create(context) {
        const rules = no_extra_semi_1.default.create(context);
        return Object.assign(Object.assign({}, rules), { ClassProperty(node) {
                rules.MethodDefinition(node);
            } });
    },
});
//# sourceMappingURL=no-extra-semi.js.map