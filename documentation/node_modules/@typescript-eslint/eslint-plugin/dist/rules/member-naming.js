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
    name: 'member-naming',
    meta: {
        type: 'suggestion',
        docs: {
            description: 'Enforces naming conventions for class members by visibility',
            category: 'Stylistic Issues',
            recommended: false,
        },
        deprecated: true,
        replacedBy: ['naming-convention'],
        messages: {
            incorrectName: '{{accessibility}} property {{name}} should match {{convention}}.',
        },
        schema: [
            {
                type: 'object',
                properties: {
                    public: {
                        type: 'string',
                        minLength: 1,
                        format: 'regex',
                    },
                    protected: {
                        type: 'string',
                        minLength: 1,
                        format: 'regex',
                    },
                    private: {
                        type: 'string',
                        minLength: 1,
                        format: 'regex',
                    },
                },
                additionalProperties: false,
                minProperties: 1,
            },
        ],
    },
    defaultOptions: [{}],
    create(context, [config]) {
        const sourceCode = context.getSourceCode();
        const conventions = Object.keys(config).reduce((acc, accessibility) => {
            acc[accessibility] = new RegExp(config[accessibility]);
            return acc;
        }, {});
        function getParameterNode(node) {
            if (node.parameter.type === experimental_utils_1.AST_NODE_TYPES.AssignmentPattern) {
                return node.parameter.left;
            }
            if (node.parameter.type === experimental_utils_1.AST_NODE_TYPES.Identifier) {
                return node.parameter;
            }
            return null;
        }
        function validateParameterName(node) {
            const parameterNode = getParameterNode(node);
            if (!parameterNode) {
                return;
            }
            validate(parameterNode, parameterNode.name, node.accessibility);
        }
        function validateName(node) {
            if (node.type === experimental_utils_1.AST_NODE_TYPES.MethodDefinition &&
                node.kind === 'constructor') {
                return;
            }
            validate(node.key, util.getNameFromMember(node, sourceCode), node.accessibility);
        }
        /**
         * Check that the name matches the convention for its accessibility.
         * @param {ASTNode}   node the named node to evaluate.
         * @param {string}    name
         * @param {Modifiers} accessibility
         * @returns {void}
         * @private
         */
        function validate(node, name, accessibility = 'public') {
            const convention = conventions[accessibility];
            if (!convention || convention.test(name)) {
                return;
            }
            context.report({
                node,
                messageId: 'incorrectName',
                data: { accessibility, name, convention },
            });
        }
        return {
            TSParameterProperty: validateParameterName,
            MethodDefinition: validateName,
            ClassProperty: validateName,
        };
    },
});
//# sourceMappingURL=member-naming.js.map