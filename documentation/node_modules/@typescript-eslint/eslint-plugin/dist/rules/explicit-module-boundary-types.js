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
const explicitReturnTypeUtils_1 = require("../util/explicitReturnTypeUtils");
exports.default = util.createRule({
    name: 'explicit-module-boundary-types',
    meta: {
        type: 'problem',
        docs: {
            description: "Require explicit return and argument types on exported functions' and classes' public class methods",
            category: 'Stylistic Issues',
            recommended: false,
        },
        messages: {
            missingReturnType: 'Missing return type on function.',
            missingArgType: "Argument '{{name}}' should be typed.",
        },
        schema: [
            {
                type: 'object',
                properties: {
                    allowTypedFunctionExpressions: {
                        type: 'boolean',
                    },
                    allowHigherOrderFunctions: {
                        type: 'boolean',
                    },
                    allowDirectConstAssertionInArrowFunctions: {
                        type: 'boolean',
                    },
                    allowedNames: {
                        type: 'array',
                        items: {
                            type: 'string',
                        },
                    },
                    shouldTrackReferences: {
                        type: 'boolean',
                    },
                },
                additionalProperties: false,
            },
        ],
    },
    defaultOptions: [
        {
            allowTypedFunctionExpressions: true,
            allowHigherOrderFunctions: true,
            allowDirectConstAssertionInArrowFunctions: true,
            allowedNames: [],
            shouldTrackReferences: true,
        },
    ],
    create(context, [options]) {
        const sourceCode = context.getSourceCode();
        function isUnexported(node) {
            let isReturnedValue = false;
            while (node) {
                if (node.type === experimental_utils_1.AST_NODE_TYPES.ExportDefaultDeclaration ||
                    node.type === experimental_utils_1.AST_NODE_TYPES.ExportNamedDeclaration ||
                    node.type === experimental_utils_1.AST_NODE_TYPES.ExportSpecifier) {
                    return false;
                }
                if (node.type === experimental_utils_1.AST_NODE_TYPES.JSXExpressionContainer) {
                    return true;
                }
                if (node.type === experimental_utils_1.AST_NODE_TYPES.ReturnStatement) {
                    isReturnedValue = true;
                }
                if (node.type === experimental_utils_1.AST_NODE_TYPES.ArrowFunctionExpression ||
                    node.type === experimental_utils_1.AST_NODE_TYPES.FunctionDeclaration ||
                    node.type === experimental_utils_1.AST_NODE_TYPES.FunctionExpression) {
                    isReturnedValue = false;
                }
                if (node.type === experimental_utils_1.AST_NODE_TYPES.BlockStatement && !isReturnedValue) {
                    return true;
                }
                node = node.parent;
            }
            return true;
        }
        function isArgumentUntyped(node) {
            return (!node.typeAnnotation ||
                node.typeAnnotation.typeAnnotation.type === experimental_utils_1.AST_NODE_TYPES.TSAnyKeyword);
        }
        /**
         * Checks if a function declaration/expression has a return type.
         */
        function checkArguments(node) {
            const paramIdentifiers = node.params.filter(util.isIdentifier);
            const untypedArgs = paramIdentifiers.filter(isArgumentUntyped);
            untypedArgs.forEach(untypedArg => context.report({
                node,
                messageId: 'missingArgType',
                data: {
                    name: untypedArg.name,
                },
            }));
        }
        /**
         * Checks if a function name is allowed and should not be checked.
         */
        function isAllowedName(node) {
            if (!node || !options.allowedNames || !options.allowedNames.length) {
                return false;
            }
            if (node.type === experimental_utils_1.AST_NODE_TYPES.VariableDeclarator) {
                return (node.id.type === experimental_utils_1.AST_NODE_TYPES.Identifier &&
                    options.allowedNames.includes(node.id.name));
            }
            else if (node.type === experimental_utils_1.AST_NODE_TYPES.MethodDefinition ||
                node.type === experimental_utils_1.AST_NODE_TYPES.TSAbstractMethodDefinition) {
                if (node.key.type === experimental_utils_1.AST_NODE_TYPES.Literal &&
                    typeof node.key.value === 'string') {
                    return options.allowedNames.includes(node.key.value);
                }
                if (node.key.type === experimental_utils_1.AST_NODE_TYPES.TemplateLiteral &&
                    node.key.expressions.length === 0) {
                    return options.allowedNames.includes(node.key.quasis[0].value.raw);
                }
                if (!node.computed && node.key.type === experimental_utils_1.AST_NODE_TYPES.Identifier) {
                    return options.allowedNames.includes(node.key.name);
                }
            }
            return false;
        }
        /**
         * Finds an array of a function expression node referred by a variable passed from parameters
         */
        function findFunctionExpressionsInScope(variable) {
            const writeExprs = variable.references
                .map(ref => ref.writeExpr)
                .filter((expr) => (expr === null || expr === void 0 ? void 0 : expr.type) === experimental_utils_1.AST_NODE_TYPES.FunctionExpression ||
                (expr === null || expr === void 0 ? void 0 : expr.type) === experimental_utils_1.AST_NODE_TYPES.ArrowFunctionExpression);
            return writeExprs;
        }
        /**
         * Finds a function node referred by a variable passed from parameters
         */
        function findFunctionInScope(variable) {
            if (variable.defs[0].type !== 'FunctionName') {
                return;
            }
            const functionNode = variable.defs[0].node;
            if ((functionNode === null || functionNode === void 0 ? void 0 : functionNode.type) !== experimental_utils_1.AST_NODE_TYPES.FunctionDeclaration) {
                return;
            }
            return functionNode;
        }
        /**
         * Checks if a function referred by the identifier passed from parameters follow the rule
         */
        function checkWithTrackingReferences(node) {
            var _a, _b;
            const scope = context.getScope();
            const variable = scope.set.get(node.name);
            if (!variable) {
                return;
            }
            if (variable.defs[0].type === 'ClassName') {
                const classNode = variable.defs[0].node;
                for (const classElement of classNode.body.body) {
                    if (classElement.type === experimental_utils_1.AST_NODE_TYPES.MethodDefinition &&
                        classElement.value.type === experimental_utils_1.AST_NODE_TYPES.FunctionExpression) {
                        checkFunctionExpression(classElement.value);
                    }
                    if (classElement.type === experimental_utils_1.AST_NODE_TYPES.ClassProperty &&
                        (((_a = classElement.value) === null || _a === void 0 ? void 0 : _a.type) === experimental_utils_1.AST_NODE_TYPES.FunctionExpression ||
                            ((_b = classElement.value) === null || _b === void 0 ? void 0 : _b.type) ===
                                experimental_utils_1.AST_NODE_TYPES.ArrowFunctionExpression)) {
                        checkFunctionExpression(classElement.value);
                    }
                }
            }
            const functionNode = findFunctionInScope(variable);
            if (functionNode) {
                checkFunction(functionNode);
            }
            const functionExpressions = findFunctionExpressionsInScope(variable);
            if (functionExpressions && functionExpressions.length > 0) {
                for (const functionExpression of functionExpressions) {
                    checkFunctionExpression(functionExpression);
                }
            }
        }
        /**
         * Checks if a function expression follow the rule
         */
        function checkFunctionExpression(node) {
            var _a;
            if (((_a = node.parent) === null || _a === void 0 ? void 0 : _a.type) === experimental_utils_1.AST_NODE_TYPES.MethodDefinition &&
                node.parent.accessibility === 'private') {
                // don't check private methods as they aren't part of the public signature
                return;
            }
            if (isAllowedName(node.parent) ||
                explicitReturnTypeUtils_1.isTypedFunctionExpression(node, options)) {
                return;
            }
            explicitReturnTypeUtils_1.checkFunctionExpressionReturnType(node, options, sourceCode, loc => context.report({
                node,
                loc,
                messageId: 'missingReturnType',
            }));
            checkArguments(node);
        }
        /**
         * Checks if a function follow the rule
         */
        function checkFunction(node) {
            if (isAllowedName(node.parent)) {
                return;
            }
            explicitReturnTypeUtils_1.checkFunctionReturnType(node, options, sourceCode, loc => context.report({
                node,
                loc,
                messageId: 'missingReturnType',
            }));
            checkArguments(node);
        }
        return {
            'ArrowFunctionExpression, FunctionExpression'(node) {
                if (isUnexported(node)) {
                    return;
                }
                checkFunctionExpression(node);
            },
            FunctionDeclaration(node) {
                if (isUnexported(node)) {
                    return;
                }
                checkFunction(node);
            },
            'ExportDefaultDeclaration, TSExportAssignment'(node) {
                if (!options.shouldTrackReferences) {
                    return;
                }
                let exported;
                if (node.type === experimental_utils_1.AST_NODE_TYPES.ExportDefaultDeclaration) {
                    exported = node.declaration;
                }
                else {
                    exported = node.expression;
                }
                switch (exported.type) {
                    case experimental_utils_1.AST_NODE_TYPES.Identifier: {
                        checkWithTrackingReferences(exported);
                        break;
                    }
                    case experimental_utils_1.AST_NODE_TYPES.ArrayExpression: {
                        for (const element of exported.elements) {
                            if (element.type === experimental_utils_1.AST_NODE_TYPES.Identifier) {
                                checkWithTrackingReferences(element);
                            }
                        }
                        break;
                    }
                    case experimental_utils_1.AST_NODE_TYPES.ObjectExpression: {
                        for (const property of exported.properties) {
                            if (property.type === experimental_utils_1.AST_NODE_TYPES.Property &&
                                property.value.type === experimental_utils_1.AST_NODE_TYPES.Identifier) {
                                checkWithTrackingReferences(property.value);
                            }
                        }
                        break;
                    }
                }
            },
        };
    },
});
//# sourceMappingURL=explicit-module-boundary-types.js.map