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
const tsutils = __importStar(require("tsutils"));
const ts = __importStar(require("typescript"));
const util = __importStar(require("../util"));
/**
 * The following is a list of exceptions to the rule
 * Generated via the following script.
 * This is statically defined to save making purposely invalid calls every lint run
 * ```
SUPPORTED_GLOBALS.flatMap(namespace => {
  const object = window[namespace];
    return Object.getOwnPropertyNames(object)
      .filter(
        name =>
          !name.startsWith('_') &&
          typeof object[name] === 'function',
      )
      .map(name => {
        try {
          const x = object[name];
          x();
        } catch (e) {
          if (e.message.includes("called on non-object")) {
            return `${namespace}.${name}`;
          }
        }
      });
}).filter(Boolean);
   * ```
 */
const nativelyNotBoundMembers = new Set([
    'Promise.all',
    'Promise.race',
    'Promise.resolve',
    'Promise.reject',
    'Promise.allSettled',
    'Object.defineProperties',
    'Object.defineProperty',
    'Reflect.defineProperty',
    'Reflect.deleteProperty',
    'Reflect.get',
    'Reflect.getOwnPropertyDescriptor',
    'Reflect.getPrototypeOf',
    'Reflect.has',
    'Reflect.isExtensible',
    'Reflect.ownKeys',
    'Reflect.preventExtensions',
    'Reflect.set',
    'Reflect.setPrototypeOf',
]);
const SUPPORTED_GLOBALS = [
    'Number',
    'Object',
    'String',
    'RegExp',
    'Symbol',
    'Array',
    'Proxy',
    'Date',
    'Infinity',
    'Atomics',
    'Reflect',
    'console',
    'Math',
    'JSON',
    'Intl',
];
const nativelyBoundMembers = SUPPORTED_GLOBALS.map(namespace => {
    const object = global[namespace];
    return Object.getOwnPropertyNames(object)
        .filter(name => !name.startsWith('_') &&
        typeof object[name] === 'function')
        .map(name => `${namespace}.${name}`);
})
    .reduce((arr, names) => arr.concat(names), [])
    .filter(name => !nativelyNotBoundMembers.has(name));
const isMemberNotImported = (symbol, currentSourceFile) => {
    const { valueDeclaration } = symbol;
    if (!valueDeclaration) {
        // working around https://github.com/microsoft/TypeScript/issues/31294
        return false;
    }
    return (!!currentSourceFile &&
        currentSourceFile !== valueDeclaration.getSourceFile());
};
const getNodeName = (node) => node.type === experimental_utils_1.AST_NODE_TYPES.Identifier ? node.name : null;
const getMemberFullName = (node) => `${getNodeName(node.object)}.${getNodeName(node.property)}`;
exports.default = util.createRule({
    name: 'unbound-method',
    meta: {
        docs: {
            category: 'Best Practices',
            description: 'Enforces unbound methods are called with their expected scope',
            recommended: 'error',
            requiresTypeChecking: true,
        },
        messages: {
            unbound: 'Avoid referencing unbound methods which may cause unintentional scoping of `this`.',
        },
        schema: [
            {
                type: 'object',
                properties: {
                    ignoreStatic: {
                        type: 'boolean',
                    },
                },
                additionalProperties: false,
            },
        ],
        type: 'problem',
    },
    defaultOptions: [
        {
            ignoreStatic: false,
        },
    ],
    create(context, [{ ignoreStatic }]) {
        const parserServices = util.getParserServices(context);
        const checker = parserServices.program.getTypeChecker();
        const currentSourceFile = parserServices.program.getSourceFile(context.getFilename());
        return {
            'MemberExpression, OptionalMemberExpression'(node) {
                if (isSafeUse(node)) {
                    return;
                }
                const objectSymbol = checker.getSymbolAtLocation(parserServices.esTreeNodeToTSNodeMap.get(node.object));
                if (objectSymbol &&
                    nativelyBoundMembers.includes(getMemberFullName(node)) &&
                    isMemberNotImported(objectSymbol, currentSourceFile)) {
                    return;
                }
                const originalNode = parserServices.esTreeNodeToTSNodeMap.get(node);
                const symbol = checker.getSymbolAtLocation(originalNode);
                if (symbol && isDangerousMethod(symbol, ignoreStatic)) {
                    context.report({
                        messageId: 'unbound',
                        node,
                    });
                }
            },
        };
    },
});
function isDangerousMethod(symbol, ignoreStatic) {
    var _a;
    const { valueDeclaration } = symbol;
    if (!valueDeclaration) {
        // working around https://github.com/microsoft/TypeScript/issues/31294
        return false;
    }
    switch (valueDeclaration.kind) {
        case ts.SyntaxKind.PropertyDeclaration:
            return (((_a = valueDeclaration.initializer) === null || _a === void 0 ? void 0 : _a.kind) ===
                ts.SyntaxKind.FunctionExpression);
        case ts.SyntaxKind.MethodDeclaration:
        case ts.SyntaxKind.MethodSignature:
            return !(ignoreStatic &&
                tsutils.hasModifier(valueDeclaration.modifiers, ts.SyntaxKind.StaticKeyword));
    }
    return false;
}
function isSafeUse(node) {
    const parent = node.parent;
    switch (parent === null || parent === void 0 ? void 0 : parent.type) {
        case experimental_utils_1.AST_NODE_TYPES.IfStatement:
        case experimental_utils_1.AST_NODE_TYPES.ForStatement:
        case experimental_utils_1.AST_NODE_TYPES.MemberExpression:
        case experimental_utils_1.AST_NODE_TYPES.OptionalMemberExpression:
        case experimental_utils_1.AST_NODE_TYPES.SwitchStatement:
        case experimental_utils_1.AST_NODE_TYPES.UpdateExpression:
        case experimental_utils_1.AST_NODE_TYPES.WhileStatement:
            return true;
        case experimental_utils_1.AST_NODE_TYPES.CallExpression:
        case experimental_utils_1.AST_NODE_TYPES.OptionalCallExpression:
            return parent.callee === node;
        case experimental_utils_1.AST_NODE_TYPES.ConditionalExpression:
            return parent.test === node;
        case experimental_utils_1.AST_NODE_TYPES.TaggedTemplateExpression:
            return parent.tag === node;
        case experimental_utils_1.AST_NODE_TYPES.UnaryExpression:
            // the first case is safe for obvious
            // reasons. The second one is also fine
            // since we're returning something falsy
            return ['typeof', '!', 'void', 'delete'].includes(parent.operator);
        case experimental_utils_1.AST_NODE_TYPES.BinaryExpression:
            return ['instanceof', '==', '!=', '===', '!=='].includes(parent.operator);
        case experimental_utils_1.AST_NODE_TYPES.AssignmentExpression:
            return parent.operator === '=' && node === parent.left;
        case experimental_utils_1.AST_NODE_TYPES.TSNonNullExpression:
        case experimental_utils_1.AST_NODE_TYPES.TSAsExpression:
        case experimental_utils_1.AST_NODE_TYPES.TSTypeAssertion:
            return isSafeUse(parent);
        case experimental_utils_1.AST_NODE_TYPES.LogicalExpression:
            if (parent.operator === '&&' && parent.left === node) {
                // this is safe, as && will return the left if and only if it's falsy
                return true;
            }
            // in all other cases, it's likely the logical expression will return the method ref
            // so make sure the parent is a safe usage
            return isSafeUse(parent);
    }
    return false;
}
//# sourceMappingURL=unbound-method.js.map