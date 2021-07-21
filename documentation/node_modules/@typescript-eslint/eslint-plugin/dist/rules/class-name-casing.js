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
exports.default = util.createRule({
    name: 'class-name-casing',
    meta: {
        type: 'suggestion',
        docs: {
            description: 'Require PascalCased class and interface names',
            category: 'Best Practices',
            recommended: 'error',
        },
        deprecated: true,
        replacedBy: ['naming-convention'],
        messages: {
            notPascalCased: "{{friendlyName}} '{{name}}' must be PascalCased.",
        },
        schema: [
            {
                type: 'object',
                properties: {
                    allowUnderscorePrefix: {
                        type: 'boolean',
                        default: false,
                    },
                },
                additionalProperties: false,
            },
        ],
    },
    defaultOptions: [{ allowUnderscorePrefix: false }],
    create(context, [options]) {
        const UNDERSCORE = '_';
        /**
         * Determine if the string is Upper cased
         * @param str
         */
        function isUpperCase(str) {
            return str === str.toUpperCase();
        }
        /**
         * Determine if the identifier name is PascalCased
         * @param name The identifier name
         */
        function isPascalCase(name) {
            const startIndex = options.allowUnderscorePrefix && name.startsWith(UNDERSCORE) ? 1 : 0;
            return (isUpperCase(name.charAt(startIndex)) &&
                !name.includes(UNDERSCORE, startIndex));
        }
        /**
         * Report a class declaration as invalid
         * @param decl The declaration
         * @param id The name of the declaration
         */
        function report(decl, id) {
            let friendlyName;
            switch (decl.type) {
                case experimental_utils_1.AST_NODE_TYPES.ClassDeclaration:
                case experimental_utils_1.AST_NODE_TYPES.ClassExpression:
                    friendlyName = decl.abstract ? 'Abstract class' : 'Class';
                    break;
                case experimental_utils_1.AST_NODE_TYPES.TSInterfaceDeclaration:
                    friendlyName = 'Interface';
                    break;
            }
            context.report({
                node: id,
                messageId: 'notPascalCased',
                data: {
                    friendlyName,
                    name: id.name,
                },
            });
        }
        return {
            'ClassDeclaration, TSInterfaceDeclaration, ClassExpression'(node) {
                // class expressions (i.e. export default class {}) are OK
                if (node.id && !isPascalCase(node.id.name)) {
                    report(node, node.id);
                }
            },
            "VariableDeclarator[init.type='ClassExpression']"(node) {
                if (node.id.type === experimental_utils_1.AST_NODE_TYPES.ArrayPattern ||
                    node.id.type === experimental_utils_1.AST_NODE_TYPES.ObjectPattern) {
                    // TODO - handle the BindingPattern case maybe?
                    /*
                    // this example makes me barf, but it's valid code
                    var { bar } = class {
                      static bar() { return 2 }
                    }
                    */
                }
                else {
                    const id = node.id;
                    const nodeInit = node.init;
                    if (id && !nodeInit.id && !isPascalCase(id.name)) {
                        report(nodeInit, id);
                    }
                }
            },
        };
    },
});
//# sourceMappingURL=class-name-casing.js.map