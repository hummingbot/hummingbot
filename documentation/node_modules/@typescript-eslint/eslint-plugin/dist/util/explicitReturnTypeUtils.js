"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const experimental_utils_1 = require("@typescript-eslint/experimental-utils");
const astUtils_1 = require("./astUtils");
const nullThrows_1 = require("./nullThrows");
/**
 * Creates a report location for the given function.
 * The location only encompasses the "start" of the function, and not the body
 *
 * eg.
 * function foo(args) {}
 * ^^^^^^^^^^^^^^^^^^
 *
 * get y(args) {}
 * ^^^^^^^^^^^
 *
 * const x = (args) => {}
 *           ^^^^^^^^^
 */
function getReporLoc(node, sourceCode) {
    /**
     * Returns start column position
     * @param node
     */
    function getLocStart() {
        /* highlight method name */
        const parent = node.parent;
        if (parent &&
            (parent.type === experimental_utils_1.AST_NODE_TYPES.MethodDefinition ||
                (parent.type === experimental_utils_1.AST_NODE_TYPES.Property && parent.method))) {
            return parent.loc.start;
        }
        return node.loc.start;
    }
    /**
     * Returns end column position
     * @param node
     */
    function getLocEnd() {
        /* highlight `=>` */
        if (node.type === experimental_utils_1.AST_NODE_TYPES.ArrowFunctionExpression) {
            return sourceCode.getTokenBefore(node.body, token => token.type === experimental_utils_1.AST_TOKEN_TYPES.Punctuator && token.value === '=>').loc.end;
        }
        return sourceCode.getTokenBefore(node.body).loc.end;
    }
    return {
        start: getLocStart(),
        end: getLocEnd(),
    };
}
/**
 * Checks if a node is a variable declarator with a type annotation.
 * ```
 * const x: Foo = ...
 * ```
 */
function isVariableDeclaratorWithTypeAnnotation(node) {
    return (node.type === experimental_utils_1.AST_NODE_TYPES.VariableDeclarator && !!node.id.typeAnnotation);
}
/**
 * Checks if a node is a class property with a type annotation.
 * ```
 * public x: Foo = ...
 * ```
 */
function isClassPropertyWithTypeAnnotation(node) {
    return node.type === experimental_utils_1.AST_NODE_TYPES.ClassProperty && !!node.typeAnnotation;
}
/**
 * Checks if a node belongs to:
 * ```
 * new Foo(() => {})
 *         ^^^^^^^^
 * ```
 */
function isConstructorArgument(node) {
    return node.type === experimental_utils_1.AST_NODE_TYPES.NewExpression;
}
/**
 * Checks if a node belongs to:
 * ```
 * const x: Foo = { prop: () => {} }
 * const x = { prop: () => {} } as Foo
 * const x = <Foo>{ prop: () => {} }
 * ```
 */
function isPropertyOfObjectWithType(property) {
    if (!property || property.type !== experimental_utils_1.AST_NODE_TYPES.Property) {
        return false;
    }
    const objectExpr = property.parent; // this shouldn't happen, checking just in case
    /* istanbul ignore if */ if (!objectExpr ||
        objectExpr.type !== experimental_utils_1.AST_NODE_TYPES.ObjectExpression) {
        return false;
    }
    const parent = objectExpr.parent; // this shouldn't happen, checking just in case
    /* istanbul ignore if */ if (!parent) {
        return false;
    }
    return (astUtils_1.isTypeAssertion(parent) ||
        isClassPropertyWithTypeAnnotation(parent) ||
        isVariableDeclaratorWithTypeAnnotation(parent) ||
        isFunctionArgument(parent));
}
/**
 * Checks if a function belongs to:
 * ```
 * () => () => ...
 * () => function () { ... }
 * () => { return () => ... }
 * () => { return function () { ... } }
 * function fn() { return () => ... }
 * function fn() { return function() { ... } }
 * ```
 */
function doesImmediatelyReturnFunctionExpression({ body, }) {
    // Should always have a body; really checking just in case
    /* istanbul ignore if */ if (!body) {
        return false;
    }
    // Check if body is a block with a single statement
    if (body.type === experimental_utils_1.AST_NODE_TYPES.BlockStatement && body.body.length === 1) {
        const [statement] = body.body;
        // Check if that statement is a return statement with an argument
        if (statement.type === experimental_utils_1.AST_NODE_TYPES.ReturnStatement &&
            !!statement.argument) {
            // If so, check that returned argument as body
            body = statement.argument;
        }
    }
    // Check if the body being returned is a function expression
    return (body.type === experimental_utils_1.AST_NODE_TYPES.ArrowFunctionExpression ||
        body.type === experimental_utils_1.AST_NODE_TYPES.FunctionExpression);
}
/**
 * Checks if a node belongs to:
 * ```
 * foo(() => 1)
 * ```
 */
function isFunctionArgument(parent, callee) {
    return ((parent.type === experimental_utils_1.AST_NODE_TYPES.CallExpression ||
        parent.type === experimental_utils_1.AST_NODE_TYPES.OptionalCallExpression) &&
        // make sure this isn't an IIFE
        parent.callee !== callee);
}
/**
 * Checks if a function belongs to:
 * ```
 * () => ({ action: 'xxx' } as const)
 * ```
 */
function returnsConstAssertionDirectly(node) {
    const { body } = node;
    if (astUtils_1.isTypeAssertion(body)) {
        const { typeAnnotation } = body;
        if (typeAnnotation.type === experimental_utils_1.AST_NODE_TYPES.TSTypeReference) {
            const { typeName } = typeAnnotation;
            if (typeName.type === experimental_utils_1.AST_NODE_TYPES.Identifier &&
                typeName.name === 'const') {
                return true;
            }
        }
    }
    return false;
}
/**
 * Checks if a function declaration/expression has a return type.
 */
function checkFunctionReturnType(node, options, sourceCode, report) {
    if (options.allowHigherOrderFunctions &&
        doesImmediatelyReturnFunctionExpression(node)) {
        return;
    }
    if (node.returnType || astUtils_1.isConstructor(node.parent) || astUtils_1.isSetter(node.parent)) {
        return;
    }
    report(getReporLoc(node, sourceCode));
}
exports.checkFunctionReturnType = checkFunctionReturnType;
function isTypedFunctionExpression(node, options) {
    const parent = nullThrows_1.nullThrows(node.parent, nullThrows_1.NullThrowsReasons.MissingParent);
    if (!options.allowTypedFunctionExpressions) {
        return false;
    }
    return (astUtils_1.isTypeAssertion(parent) ||
        isVariableDeclaratorWithTypeAnnotation(parent) ||
        isClassPropertyWithTypeAnnotation(parent) ||
        isPropertyOfObjectWithType(parent) ||
        isFunctionArgument(parent, node) ||
        isConstructorArgument(parent));
}
exports.isTypedFunctionExpression = isTypedFunctionExpression;
/**
 * Checks if a function declaration/expression has a return type.
 */
function checkFunctionExpressionReturnType(node, options, sourceCode, report) {
    if (isTypedFunctionExpression(node, options)) {
        return;
    }
    const parent = nullThrows_1.nullThrows(node.parent, nullThrows_1.NullThrowsReasons.MissingParent);
    if (options.allowExpressions &&
        parent.type !== experimental_utils_1.AST_NODE_TYPES.VariableDeclarator &&
        parent.type !== experimental_utils_1.AST_NODE_TYPES.MethodDefinition &&
        parent.type !== experimental_utils_1.AST_NODE_TYPES.ExportDefaultDeclaration &&
        parent.type !== experimental_utils_1.AST_NODE_TYPES.ClassProperty) {
        return;
    }
    // https://github.com/typescript-eslint/typescript-eslint/issues/653
    if (options.allowDirectConstAssertionInArrowFunctions &&
        node.type === experimental_utils_1.AST_NODE_TYPES.ArrowFunctionExpression &&
        returnsConstAssertionDirectly(node)) {
        return;
    }
    checkFunctionReturnType(node, options, sourceCode, report);
}
exports.checkFunctionExpressionReturnType = checkFunctionExpressionReturnType;
//# sourceMappingURL=explicitReturnTypeUtils.js.map