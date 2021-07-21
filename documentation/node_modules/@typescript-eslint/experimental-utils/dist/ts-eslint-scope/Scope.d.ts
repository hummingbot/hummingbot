import { TSESTree } from '../ts-estree';
import { Definition } from './Definition';
import { Reference, ReferenceFlag } from './Reference';
import { ScopeManager } from './ScopeManager';
import { Variable } from './Variable';
declare type ScopeType = 'block' | 'catch' | 'class' | 'for' | 'function' | 'function-expression-name' | 'global' | 'module' | 'switch' | 'with' | 'TDZ' | 'enum' | 'empty-function';
interface Scope {
    type: ScopeType;
    isStrict: boolean;
    upper: Scope | null;
    childScopes: Scope[];
    variableScope: Scope;
    block: TSESTree.Node;
    variables: Variable[];
    set: Map<string, Variable>;
    references: Reference[];
    through: Reference[];
    thisFound?: boolean;
    taints: Map<string, boolean>;
    functionExpressionScope: boolean;
    __left: Reference[];
    __shouldStaticallyClose(scopeManager: ScopeManager): boolean;
    __shouldStaticallyCloseForGlobal(ref: any): boolean;
    __staticCloseRef(ref: any): void;
    __dynamicCloseRef(ref: any): void;
    __globalCloseRef(ref: any): void;
    __close(scopeManager: ScopeManager): Scope;
    __isValidResolution(ref: any, variable: any): variable is Variable;
    __resolve(ref: Reference): boolean;
    __delegateToUpperScope(ref: any): void;
    __addDeclaredVariablesOfNode(variable: any, node: TSESTree.Node): void;
    __defineGeneric(name: string, set: Map<string, Variable>, variables: Variable[], node: TSESTree.Identifier, def: Definition): void;
    __define(node: TSESTree.Node, def: Definition): void;
    __referencing(node: TSESTree.Node, assign?: ReferenceFlag, writeExpr?: TSESTree.Node, maybeImplicitGlobal?: any, partial?: any, init?: any): void;
    __detectEval(): void;
    __detectThis(): void;
    __isClosed(): boolean;
    /**
     * returns resolved {Reference}
     * @method Scope#resolve
     * @param {Espree.Identifier} ident - identifier to be resolved.
     * @returns {Reference} reference
     */
    resolve(ident: TSESTree.Node): Reference;
    /**
     * returns this scope is static
     * @method Scope#isStatic
     * @returns {boolean} static
     */
    isStatic(): boolean;
    /**
     * returns this scope has materialized arguments
     * @method Scope#isArgumentsMaterialized
     * @returns {boolean} arguments materialized
     */
    isArgumentsMaterialized(): boolean;
    /**
     * returns this scope has materialized `this` reference
     * @method Scope#isThisMaterialized
     * @returns {boolean} this materialized
     */
    isThisMaterialized(): boolean;
    isUsedName(name: any): boolean;
}
interface ScopeConstructor {
    new (scopeManager: ScopeManager, type: ScopeType, upperScope: Scope | null, block: TSESTree.Node | null, isMethodDefinition: boolean): Scope;
}
declare const Scope: ScopeConstructor;
interface ScopeChildConstructorWithUpperScope<T> {
    new (scopeManager: ScopeManager, upperScope: Scope, block: TSESTree.Node | null): T;
}
interface GlobalScope extends Scope {
}
declare const GlobalScope: ScopeConstructor & (new (scopeManager: ScopeManager, block: TSESTree.ArrayExpression | TSESTree.ArrayPattern | TSESTree.ArrowFunctionExpression | TSESTree.AssignmentExpression | TSESTree.AssignmentPattern | TSESTree.AwaitExpression | TSESTree.BigIntLiteral | TSESTree.BinaryExpression | TSESTree.BlockStatement | TSESTree.BreakStatement | TSESTree.CallExpression | TSESTree.CatchClause | TSESTree.ClassBody | TSESTree.ClassDeclaration | TSESTree.ClassExpression | TSESTree.ClassPropertyComputedName | TSESTree.ClassPropertyNonComputedName | TSESTree.ConditionalExpression | TSESTree.ContinueStatement | TSESTree.DebuggerStatement | TSESTree.Decorator | TSESTree.DoWhileStatement | TSESTree.EmptyStatement | TSESTree.ExportAllDeclaration | TSESTree.ExportDefaultDeclaration | TSESTree.ExportNamedDeclaration | TSESTree.ExportSpecifier | TSESTree.ExpressionStatement | TSESTree.ForInStatement | TSESTree.ForOfStatement | TSESTree.ForStatement | TSESTree.FunctionDeclaration | TSESTree.FunctionExpression | TSESTree.Identifier | TSESTree.IfStatement | TSESTree.Import | TSESTree.ImportDeclaration | TSESTree.ImportDefaultSpecifier | TSESTree.ImportNamespaceSpecifier | TSESTree.ImportSpecifier | TSESTree.JSXAttribute | TSESTree.JSXClosingElement | TSESTree.JSXClosingFragment | TSESTree.JSXElement | TSESTree.JSXEmptyExpression | TSESTree.JSXExpressionContainer | TSESTree.JSXFragment | TSESTree.JSXIdentifier | TSESTree.JSXOpeningElement | TSESTree.JSXOpeningFragment | TSESTree.JSXSpreadAttribute | TSESTree.JSXSpreadChild | TSESTree.JSXMemberExpression | TSESTree.JSXText | TSESTree.LabeledStatement | TSESTree.BooleanLiteral | TSESTree.NumberLiteral | TSESTree.NullLiteral | TSESTree.RegExpLiteral | TSESTree.StringLiteral | TSESTree.LogicalExpression | TSESTree.MemberExpressionComputedName | TSESTree.MemberExpressionNonComputedName | TSESTree.MetaProperty | TSESTree.MethodDefinitionComputedName | TSESTree.MethodDefinitionNonComputedName | TSESTree.NewExpression | TSESTree.ObjectExpression | TSESTree.ObjectPattern | TSESTree.OptionalCallExpression | TSESTree.OptionalMemberExpressionComputedName | TSESTree.OptionalMemberExpressionNonComputedName | TSESTree.Program | TSESTree.PropertyComputedName | TSESTree.PropertyNonComputedName | TSESTree.RestElement | TSESTree.ReturnStatement | TSESTree.SequenceExpression | TSESTree.SpreadElement | TSESTree.Super | TSESTree.SwitchCase | TSESTree.SwitchStatement | TSESTree.TaggedTemplateExpression | TSESTree.TemplateElement | TSESTree.TemplateLiteral | TSESTree.ThisExpression | TSESTree.ThrowStatement | TSESTree.TryStatement | TSESTree.TSAbstractClassPropertyComputedName | TSESTree.TSAbstractClassPropertyNonComputedName | TSESTree.TSAbstractKeyword | TSESTree.TSAbstractMethodDefinitionComputedName | TSESTree.TSAbstractMethodDefinitionNonComputedName | TSESTree.TSAnyKeyword | TSESTree.TSArrayType | TSESTree.TSAsExpression | TSESTree.TSAsyncKeyword | TSESTree.TSBigIntKeyword | TSESTree.TSBooleanKeyword | TSESTree.TSCallSignatureDeclaration | TSESTree.TSClassImplements | TSESTree.TSConditionalType | TSESTree.TSConstructorType | TSESTree.TSConstructSignatureDeclaration | TSESTree.TSDeclareFunction | TSESTree.TSDeclareKeyword | TSESTree.TSEmptyBodyFunctionExpression | TSESTree.TSEnumDeclaration | TSESTree.TSEnumMemberComputedName | TSESTree.TSEnumMemberNonComputedName | TSESTree.TSExportAssignment | TSESTree.TSExportKeyword | TSESTree.TSExternalModuleReference | TSESTree.TSFunctionType | TSESTree.TSImportEqualsDeclaration | TSESTree.TSImportType | TSESTree.TSIndexedAccessType | TSESTree.TSIndexSignature | TSESTree.TSInferType | TSESTree.TSInterfaceDeclaration | TSESTree.TSInterfaceBody | TSESTree.TSInterfaceHeritage | TSESTree.TSIntersectionType | TSESTree.TSLiteralType | TSESTree.TSMappedType | TSESTree.TSMethodSignatureComputedName | TSESTree.TSMethodSignatureNonComputedName | TSESTree.TSModuleBlock | TSESTree.TSModuleDeclaration | TSESTree.TSNamespaceExportDeclaration | TSESTree.TSNeverKeyword | TSESTree.TSNonNullExpression | TSESTree.TSNullKeyword | TSESTree.TSNumberKeyword | TSESTree.TSObjectKeyword | TSESTree.TSOptionalType | TSESTree.TSParameterProperty | TSESTree.TSParenthesizedType | TSESTree.TSPropertySignatureComputedName | TSESTree.TSPropertySignatureNonComputedName | TSESTree.TSPublicKeyword | TSESTree.TSPrivateKeyword | TSESTree.TSProtectedKeyword | TSESTree.TSQualifiedName | TSESTree.TSReadonlyKeyword | TSESTree.TSRestType | TSESTree.TSStaticKeyword | TSESTree.TSStringKeyword | TSESTree.TSSymbolKeyword | TSESTree.TSThisType | TSESTree.TSTupleType | TSESTree.TSTypeAliasDeclaration | TSESTree.TSTypeAnnotation | TSESTree.TSTypeAssertion | TSESTree.TSTypeLiteral | TSESTree.TSTypeOperator | TSESTree.TSTypeParameter | TSESTree.TSTypeParameterDeclaration | TSESTree.TSTypeParameterInstantiation | TSESTree.TSTypePredicate | TSESTree.TSTypeQuery | TSESTree.TSTypeReference | TSESTree.TSUndefinedKeyword | TSESTree.TSUnionType | TSESTree.TSUnknownKeyword | TSESTree.TSVoidKeyword | TSESTree.UpdateExpression | TSESTree.UnaryExpression | TSESTree.VariableDeclaration | TSESTree.VariableDeclarator | TSESTree.WhileStatement | TSESTree.WithStatement | TSESTree.YieldExpression | null) => GlobalScope);
interface ModuleScope extends Scope {
}
declare const ModuleScope: ScopeConstructor & ScopeChildConstructorWithUpperScope<ModuleScope>;
interface FunctionExpressionNameScope extends Scope {
}
declare const FunctionExpressionNameScope: ScopeConstructor & ScopeChildConstructorWithUpperScope<FunctionExpressionNameScope>;
interface CatchScope extends Scope {
}
declare const CatchScope: ScopeConstructor & ScopeChildConstructorWithUpperScope<CatchScope>;
interface WithScope extends Scope {
}
declare const WithScope: ScopeConstructor & ScopeChildConstructorWithUpperScope<WithScope>;
interface BlockScope extends Scope {
}
declare const BlockScope: ScopeConstructor & ScopeChildConstructorWithUpperScope<BlockScope>;
interface SwitchScope extends Scope {
}
declare const SwitchScope: ScopeConstructor & ScopeChildConstructorWithUpperScope<SwitchScope>;
interface FunctionScope extends Scope {
}
declare const FunctionScope: ScopeConstructor & (new (scopeManager: ScopeManager, upperScope: Scope, block: TSESTree.ArrayExpression | TSESTree.ArrayPattern | TSESTree.ArrowFunctionExpression | TSESTree.AssignmentExpression | TSESTree.AssignmentPattern | TSESTree.AwaitExpression | TSESTree.BigIntLiteral | TSESTree.BinaryExpression | TSESTree.BlockStatement | TSESTree.BreakStatement | TSESTree.CallExpression | TSESTree.CatchClause | TSESTree.ClassBody | TSESTree.ClassDeclaration | TSESTree.ClassExpression | TSESTree.ClassPropertyComputedName | TSESTree.ClassPropertyNonComputedName | TSESTree.ConditionalExpression | TSESTree.ContinueStatement | TSESTree.DebuggerStatement | TSESTree.Decorator | TSESTree.DoWhileStatement | TSESTree.EmptyStatement | TSESTree.ExportAllDeclaration | TSESTree.ExportDefaultDeclaration | TSESTree.ExportNamedDeclaration | TSESTree.ExportSpecifier | TSESTree.ExpressionStatement | TSESTree.ForInStatement | TSESTree.ForOfStatement | TSESTree.ForStatement | TSESTree.FunctionDeclaration | TSESTree.FunctionExpression | TSESTree.Identifier | TSESTree.IfStatement | TSESTree.Import | TSESTree.ImportDeclaration | TSESTree.ImportDefaultSpecifier | TSESTree.ImportNamespaceSpecifier | TSESTree.ImportSpecifier | TSESTree.JSXAttribute | TSESTree.JSXClosingElement | TSESTree.JSXClosingFragment | TSESTree.JSXElement | TSESTree.JSXEmptyExpression | TSESTree.JSXExpressionContainer | TSESTree.JSXFragment | TSESTree.JSXIdentifier | TSESTree.JSXOpeningElement | TSESTree.JSXOpeningFragment | TSESTree.JSXSpreadAttribute | TSESTree.JSXSpreadChild | TSESTree.JSXMemberExpression | TSESTree.JSXText | TSESTree.LabeledStatement | TSESTree.BooleanLiteral | TSESTree.NumberLiteral | TSESTree.NullLiteral | TSESTree.RegExpLiteral | TSESTree.StringLiteral | TSESTree.LogicalExpression | TSESTree.MemberExpressionComputedName | TSESTree.MemberExpressionNonComputedName | TSESTree.MetaProperty | TSESTree.MethodDefinitionComputedName | TSESTree.MethodDefinitionNonComputedName | TSESTree.NewExpression | TSESTree.ObjectExpression | TSESTree.ObjectPattern | TSESTree.OptionalCallExpression | TSESTree.OptionalMemberExpressionComputedName | TSESTree.OptionalMemberExpressionNonComputedName | TSESTree.Program | TSESTree.PropertyComputedName | TSESTree.PropertyNonComputedName | TSESTree.RestElement | TSESTree.ReturnStatement | TSESTree.SequenceExpression | TSESTree.SpreadElement | TSESTree.Super | TSESTree.SwitchCase | TSESTree.SwitchStatement | TSESTree.TaggedTemplateExpression | TSESTree.TemplateElement | TSESTree.TemplateLiteral | TSESTree.ThisExpression | TSESTree.ThrowStatement | TSESTree.TryStatement | TSESTree.TSAbstractClassPropertyComputedName | TSESTree.TSAbstractClassPropertyNonComputedName | TSESTree.TSAbstractKeyword | TSESTree.TSAbstractMethodDefinitionComputedName | TSESTree.TSAbstractMethodDefinitionNonComputedName | TSESTree.TSAnyKeyword | TSESTree.TSArrayType | TSESTree.TSAsExpression | TSESTree.TSAsyncKeyword | TSESTree.TSBigIntKeyword | TSESTree.TSBooleanKeyword | TSESTree.TSCallSignatureDeclaration | TSESTree.TSClassImplements | TSESTree.TSConditionalType | TSESTree.TSConstructorType | TSESTree.TSConstructSignatureDeclaration | TSESTree.TSDeclareFunction | TSESTree.TSDeclareKeyword | TSESTree.TSEmptyBodyFunctionExpression | TSESTree.TSEnumDeclaration | TSESTree.TSEnumMemberComputedName | TSESTree.TSEnumMemberNonComputedName | TSESTree.TSExportAssignment | TSESTree.TSExportKeyword | TSESTree.TSExternalModuleReference | TSESTree.TSFunctionType | TSESTree.TSImportEqualsDeclaration | TSESTree.TSImportType | TSESTree.TSIndexedAccessType | TSESTree.TSIndexSignature | TSESTree.TSInferType | TSESTree.TSInterfaceDeclaration | TSESTree.TSInterfaceBody | TSESTree.TSInterfaceHeritage | TSESTree.TSIntersectionType | TSESTree.TSLiteralType | TSESTree.TSMappedType | TSESTree.TSMethodSignatureComputedName | TSESTree.TSMethodSignatureNonComputedName | TSESTree.TSModuleBlock | TSESTree.TSModuleDeclaration | TSESTree.TSNamespaceExportDeclaration | TSESTree.TSNeverKeyword | TSESTree.TSNonNullExpression | TSESTree.TSNullKeyword | TSESTree.TSNumberKeyword | TSESTree.TSObjectKeyword | TSESTree.TSOptionalType | TSESTree.TSParameterProperty | TSESTree.TSParenthesizedType | TSESTree.TSPropertySignatureComputedName | TSESTree.TSPropertySignatureNonComputedName | TSESTree.TSPublicKeyword | TSESTree.TSPrivateKeyword | TSESTree.TSProtectedKeyword | TSESTree.TSQualifiedName | TSESTree.TSReadonlyKeyword | TSESTree.TSRestType | TSESTree.TSStaticKeyword | TSESTree.TSStringKeyword | TSESTree.TSSymbolKeyword | TSESTree.TSThisType | TSESTree.TSTupleType | TSESTree.TSTypeAliasDeclaration | TSESTree.TSTypeAnnotation | TSESTree.TSTypeAssertion | TSESTree.TSTypeLiteral | TSESTree.TSTypeOperator | TSESTree.TSTypeParameter | TSESTree.TSTypeParameterDeclaration | TSESTree.TSTypeParameterInstantiation | TSESTree.TSTypePredicate | TSESTree.TSTypeQuery | TSESTree.TSTypeReference | TSESTree.TSUndefinedKeyword | TSESTree.TSUnionType | TSESTree.TSUnknownKeyword | TSESTree.TSVoidKeyword | TSESTree.UpdateExpression | TSESTree.UnaryExpression | TSESTree.VariableDeclaration | TSESTree.VariableDeclarator | TSESTree.WhileStatement | TSESTree.WithStatement | TSESTree.YieldExpression | null, isMethodDefinition: boolean) => FunctionScope);
interface ForScope extends Scope {
}
declare const ForScope: ScopeConstructor & ScopeChildConstructorWithUpperScope<ForScope>;
interface ClassScope extends Scope {
}
declare const ClassScope: ScopeConstructor & ScopeChildConstructorWithUpperScope<ClassScope>;
export { ScopeType, Scope, GlobalScope, ModuleScope, FunctionExpressionNameScope, CatchScope, WithScope, BlockScope, SwitchScope, FunctionScope, ForScope, ClassScope, };
//# sourceMappingURL=Scope.d.ts.map