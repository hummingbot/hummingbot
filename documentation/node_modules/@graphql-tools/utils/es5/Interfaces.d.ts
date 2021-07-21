import { GraphQLSchema, GraphQLField, GraphQLInputType, GraphQLNamedType, GraphQLFieldResolver, GraphQLResolveInfo, GraphQLScalarType, DocumentNode, FieldNode, GraphQLEnumValue, GraphQLEnumType, GraphQLUnionType, GraphQLArgument, GraphQLInputField, GraphQLInputObjectType, GraphQLInterfaceType, GraphQLObjectType, GraphQLDirective, FragmentDefinitionNode, SelectionNode, OperationDefinitionNode, GraphQLError, ExecutionResult as GraphQLExecutionResult, GraphQLOutputType, FieldDefinitionNode, GraphQLFieldConfig, GraphQLInputFieldConfig, GraphQLArgumentConfig, GraphQLEnumValueConfig, GraphQLScalarSerializer, GraphQLScalarValueParser, GraphQLScalarLiteralParser, ScalarTypeDefinitionNode, ScalarTypeExtensionNode, EnumTypeDefinitionNode, EnumTypeExtensionNode, GraphQLIsTypeOfFn, ObjectTypeDefinitionNode, ObjectTypeExtensionNode, InterfaceTypeExtensionNode, InterfaceTypeDefinitionNode, GraphQLTypeResolver, UnionTypeDefinitionNode, UnionTypeExtensionNode, InputObjectTypeExtensionNode, InputObjectTypeDefinitionNode, GraphQLType } from 'graphql';
import { SchemaVisitor } from './SchemaVisitor';
export interface ExecutionResult<TData = Record<string, any>> extends GraphQLExecutionResult {
    data?: TData | null;
    extensions?: Record<string, any>;
}
export declare type Result = ExecutionResult;
export declare type TypeMap = Record<string, GraphQLNamedType>;
export interface GraphQLExecutionContext {
    schema: GraphQLSchema;
    fragments: Record<string, FragmentDefinitionNode>;
    rootValue: any;
    contextValue: any;
    operation: OperationDefinitionNode;
    variableValues: Record<string, any>;
    fieldResolver: GraphQLFieldResolver<any, any>;
    errors: Array<GraphQLError>;
}
export interface GraphQLParseOptions {
    noLocation?: boolean;
    allowLegacySDLEmptyFields?: boolean;
    allowLegacySDLImplementsInterfaces?: boolean;
    experimentalFragmentVariables?: boolean;
}
/**
 * Options for validating resolvers
 */
export interface IResolverValidationOptions {
    /**
     * Set to `true` to require a resolver to be defined for any field that has
     * arguments. Defaults to `false`.
     */
    requireResolversForArgs?: boolean;
    /**
     * Set to `true` to require a resolver to be defined for any field which has
     * a return type that isn't a scalar. Defaults to `false`.
     */
    requireResolversForNonScalar?: boolean;
    /**
     * Set to `true` to require a resolver for be defined for all fields defined
     * in the schema. Defaults to `false`.
     */
    requireResolversForAllFields?: boolean;
    /**
     * Set to `true` to require a `resolveType()` for Interface and Union types.
     * Defaults to `false`.
     */
    requireResolversForResolveType?: boolean;
    /**
     * Set to `false` to require all defined resolvers to match fields that
     * actually exist in the schema. Defaults to `true`.
     */
    allowResolversNotInSchema?: boolean;
}
/**
 * Configuration object for adding resolvers to a schema
 */
export interface IAddResolversToSchemaOptions {
    /**
     * The schema to which to add resolvers
     */
    schema: GraphQLSchema;
    /**
     * Object describing the field resolvers to add to the provided schema
     */
    resolvers: IResolvers;
    /**
     * Override the default field resolver provided by `graphql-js`
     */
    defaultFieldResolver?: IFieldResolver<any, any>;
    /**
     * Additional options for validating the provided resolvers
     */
    resolverValidationOptions?: IResolverValidationOptions;
    /**
     * GraphQL object types that implement interfaces will inherit any missing
     * resolvers from their interface types defined in the `resolvers` object
     */
    inheritResolversFromInterfaces?: boolean;
    /**
     * Set to `true` to modify the existing schema instead of creating a new one
     */
    updateResolversInPlace?: boolean;
}
export declare type IScalarTypeResolver = GraphQLScalarType & {
    __name?: string;
    __description?: string;
    __serialize?: GraphQLScalarSerializer<any>;
    __parseValue?: GraphQLScalarValueParser<any>;
    __parseLiteral?: GraphQLScalarLiteralParser<any>;
    __extensions?: Record<string, any>;
    __astNode?: ScalarTypeDefinitionNode;
    __extensionASTNodes?: Array<ScalarTypeExtensionNode>;
};
export declare type IEnumTypeResolver = Record<string, any> & {
    __name?: string;
    __description?: string;
    __extensions?: Record<string, any>;
    __astNode?: EnumTypeDefinitionNode;
    __extensionASTNodes?: Array<EnumTypeExtensionNode>;
};
export interface IFieldResolverOptions<TSource = any, TContext = any, TArgs = any> {
    name?: string;
    description?: string;
    type?: GraphQLOutputType;
    args?: Array<GraphQLArgument>;
    resolve?: IFieldResolver<TSource, TContext, TArgs>;
    subscribe?: IFieldResolver<TSource, TContext, TArgs>;
    isDeprecated?: boolean;
    deprecationReason?: string;
    extensions?: Record<string, any>;
    astNode?: FieldDefinitionNode;
}
export declare type SchemaTransform = (originalSchema: GraphQLSchema) => GraphQLSchema;
export declare type RequestTransform<T = Record<string, any>> = (originalRequest: Request, delegationContext?: Record<string, any>, transformationContext?: T) => Request;
export declare type ResultTransform<T = Record<string, any>> = (originalResult: ExecutionResult, delegationContext?: Record<string, any>, transformationContext?: T) => ExecutionResult;
export interface Transform<T = Record<string, any>> {
    transformSchema?: SchemaTransform;
    transformRequest?: RequestTransform<T>;
    transformResult?: ResultTransform<T>;
}
export declare type FieldNodeMapper = (fieldNode: FieldNode, fragments: Record<string, FragmentDefinitionNode>, transformationContext: Record<string, any>) => SelectionNode | Array<SelectionNode>;
export declare type FieldNodeMappers = Record<string, Record<string, FieldNodeMapper>>;
export declare type InputFieldFilter = (typeName?: string, fieldName?: string, inputFieldConfig?: GraphQLInputFieldConfig) => boolean;
export declare type FieldFilter = (typeName?: string, fieldName?: string, fieldConfig?: GraphQLFieldConfig<any, any>) => boolean;
export declare type RootFieldFilter = (operation?: 'Query' | 'Mutation' | 'Subscription', rootFieldName?: string, fieldConfig?: GraphQLFieldConfig<any, any>) => boolean;
export declare type TypeFilter = (typeName: string, type: GraphQLType) => boolean;
export declare type RenameTypesOptions = {
    renameBuiltins: boolean;
    renameScalars: boolean;
};
export declare type IFieldResolver<TSource, TContext, TArgs = Record<string, any>, TReturn = any> = (source: TSource, args: TArgs, context: TContext, info: GraphQLResolveInfo) => TReturn;
export declare type ITypedef = (() => Array<ITypedef>) | string | DocumentNode;
export declare type ITypeDefinitions = ITypedef | Array<ITypedef>;
export declare type IObjectTypeResolver<TSource = any, TContext = any, TArgs = any> = {
    [key: string]: IFieldResolver<TSource, TContext, TArgs> | IFieldResolverOptions<TSource, TContext>;
} & {
    __name?: string;
    __description?: string;
    __isTypeOf?: GraphQLIsTypeOfFn<TSource, TContext>;
    __extensions?: Record<string, any>;
    __astNode?: ObjectTypeDefinitionNode;
    __extensionASTNodes?: ObjectTypeExtensionNode;
};
export declare type IInterfaceTypeResolver<TSource = any, TContext = any, TArgs = any> = {
    [key: string]: IFieldResolver<TSource, TContext, TArgs> | IFieldResolverOptions<TSource, TContext>;
} & {
    __name?: string;
    __description?: string;
    __resolveType?: GraphQLTypeResolver<any, any>;
    __extensions?: Record<string, any>;
    __astNode?: InterfaceTypeDefinitionNode;
    __extensionASTNodes?: Array<InterfaceTypeExtensionNode>;
};
export declare type IUnionTypeResolver = {
    __name?: string;
    __description?: string;
    __resolveType?: GraphQLTypeResolver<any, any>;
    __extensions?: Record<string, any>;
    __astNode?: UnionTypeDefinitionNode;
    __extensionASTNodes?: Array<UnionTypeExtensionNode>;
};
export declare type IInputObjectTypeResolver = {
    __name?: string;
    __description?: string;
    __extensions?: Record<string, any>;
    __astNode?: InputObjectTypeDefinitionNode;
    __extensionASTNodes?: Array<InputObjectTypeExtensionNode>;
};
export declare type ISchemaLevelResolver<TSource, TContext, TArgs = Record<string, any>, TReturn = any> = IFieldResolver<TSource, TContext, TArgs, TReturn>;
export declare type IResolvers<TSource = any, TContext = any, TArgs = Record<string, any>, TReturn = any> = Record<string, ISchemaLevelResolver<TSource, TContext, TArgs, TReturn> | IObjectTypeResolver<TSource, TContext> | IInterfaceTypeResolver<TSource, TContext> | IUnionTypeResolver | IScalarTypeResolver | IEnumTypeResolver | IInputObjectTypeResolver>;
export declare type IFieldIteratorFn = (fieldDef: GraphQLField<any, any>, typeName: string, fieldName: string) => void;
export declare type IDefaultValueIteratorFn = (type: GraphQLInputType, value: any) => void;
export declare type NextResolverFn = () => Promise<any>;
export declare type DirectiveResolverFn<TSource = any, TContext = any> = (next: NextResolverFn, source: TSource, args: {
    [argName: string]: any;
}, context: TContext, info: GraphQLResolveInfo) => any;
export interface IDirectiveResolvers<TSource = any, TContext = any> {
    [directiveName: string]: DirectiveResolverFn<TSource, TContext>;
}
export declare type Operation = 'query' | 'mutation' | 'subscription';
export interface Request {
    document: DocumentNode;
    variables: Record<string, any>;
    extensions?: Record<string, any>;
}
export declare type VisitableSchemaType = GraphQLSchema | GraphQLObjectType | GraphQLInterfaceType | GraphQLInputObjectType | GraphQLNamedType | GraphQLScalarType | GraphQLField<any, any> | GraphQLInputField | GraphQLArgument | GraphQLUnionType | GraphQLEnumType | GraphQLEnumValue;
export declare type VisitorSelector = (type: VisitableSchemaType, methodName: string) => Array<SchemaVisitor | SchemaVisitorMap>;
export declare enum VisitSchemaKind {
    TYPE = "VisitSchemaKind.TYPE",
    SCALAR_TYPE = "VisitSchemaKind.SCALAR_TYPE",
    ENUM_TYPE = "VisitSchemaKind.ENUM_TYPE",
    COMPOSITE_TYPE = "VisitSchemaKind.COMPOSITE_TYPE",
    OBJECT_TYPE = "VisitSchemaKind.OBJECT_TYPE",
    INPUT_OBJECT_TYPE = "VisitSchemaKind.INPUT_OBJECT_TYPE",
    ABSTRACT_TYPE = "VisitSchemaKind.ABSTRACT_TYPE",
    UNION_TYPE = "VisitSchemaKind.UNION_TYPE",
    INTERFACE_TYPE = "VisitSchemaKind.INTERFACE_TYPE",
    ROOT_OBJECT = "VisitSchemaKind.ROOT_OBJECT",
    QUERY = "VisitSchemaKind.QUERY",
    MUTATION = "VisitSchemaKind.MUTATION",
    SUBSCRIPTION = "VisitSchemaKind.SUBSCRIPTION"
}
export interface SchemaVisitorMap {
    [VisitSchemaKind.TYPE]?: NamedTypeVisitor;
    [VisitSchemaKind.SCALAR_TYPE]?: ScalarTypeVisitor;
    [VisitSchemaKind.ENUM_TYPE]?: EnumTypeVisitor;
    [VisitSchemaKind.COMPOSITE_TYPE]?: CompositeTypeVisitor;
    [VisitSchemaKind.OBJECT_TYPE]?: ObjectTypeVisitor;
    [VisitSchemaKind.INPUT_OBJECT_TYPE]?: InputObjectTypeVisitor;
    [VisitSchemaKind.ABSTRACT_TYPE]?: AbstractTypeVisitor;
    [VisitSchemaKind.UNION_TYPE]?: UnionTypeVisitor;
    [VisitSchemaKind.INTERFACE_TYPE]?: InterfaceTypeVisitor;
    [VisitSchemaKind.ROOT_OBJECT]?: ObjectTypeVisitor;
    [VisitSchemaKind.QUERY]?: ObjectTypeVisitor;
    [VisitSchemaKind.MUTATION]?: ObjectTypeVisitor;
    [VisitSchemaKind.SUBSCRIPTION]?: ObjectTypeVisitor;
}
export declare type NamedTypeVisitor = (type: GraphQLNamedType, schema: GraphQLSchema) => GraphQLNamedType | null | undefined;
export declare type ScalarTypeVisitor = (type: GraphQLScalarType, schema: GraphQLSchema) => GraphQLScalarType | null | undefined;
export declare type EnumTypeVisitor = (type: GraphQLEnumType, schema: GraphQLSchema) => GraphQLEnumType | null | undefined;
export declare type CompositeTypeVisitor = (type: GraphQLObjectType | GraphQLInterfaceType | GraphQLUnionType, schema: GraphQLSchema) => GraphQLObjectType | GraphQLInterfaceType | GraphQLUnionType | null | undefined;
export declare type ObjectTypeVisitor = (type: GraphQLObjectType, schema: GraphQLSchema) => GraphQLObjectType | null | undefined;
export declare type InputObjectTypeVisitor = (type: GraphQLInputObjectType, schema: GraphQLSchema) => GraphQLInputObjectType | null | undefined;
export declare type AbstractTypeVisitor = (type: GraphQLInterfaceType | GraphQLUnionType, schema: GraphQLSchema) => GraphQLInterfaceType | GraphQLUnionType | null | undefined;
export declare type UnionTypeVisitor = (type: GraphQLUnionType, schema: GraphQLSchema) => GraphQLUnionType | null | undefined;
export declare type InterfaceTypeVisitor = (type: GraphQLInterfaceType, schema: GraphQLSchema) => GraphQLInterfaceType | null | undefined;
export declare enum MapperKind {
    TYPE = "MapperKind.TYPE",
    SCALAR_TYPE = "MapperKind.SCALAR_TYPE",
    ENUM_TYPE = "MapperKind.ENUM_TYPE",
    COMPOSITE_TYPE = "MapperKind.COMPOSITE_TYPE",
    OBJECT_TYPE = "MapperKind.OBJECT_TYPE",
    INPUT_OBJECT_TYPE = "MapperKind.INPUT_OBJECT_TYPE",
    ABSTRACT_TYPE = "MapperKind.ABSTRACT_TYPE",
    UNION_TYPE = "MapperKind.UNION_TYPE",
    INTERFACE_TYPE = "MapperKind.INTERFACE_TYPE",
    ROOT_OBJECT = "MapperKind.ROOT_OBJECT",
    QUERY = "MapperKind.QUERY",
    MUTATION = "MapperKind.MUTATION",
    SUBSCRIPTION = "MapperKind.SUBSCRIPTION",
    DIRECTIVE = "MapperKind.DIRECTIVE",
    FIELD = "MapperKind.FIELD",
    COMPOSITE_FIELD = "MapperKind.COMPOSITE_FIELD",
    OBJECT_FIELD = "MapperKind.OBJECT_FIELD",
    ROOT_FIELD = "MapperKind.ROOT_FIELD",
    QUERY_ROOT_FIELD = "MapperKind.QUERY_ROOT_FIELD",
    MUTATION_ROOT_FIELD = "MapperKind.MUTATION_ROOT_FIELD",
    SUBSCRIPTION_ROOT_FIELD = "MapperKind.SUBSCRIPTION_ROOT_FIELD",
    INTERFACE_FIELD = "MapperKind.INTERFACE_FIELD",
    INPUT_OBJECT_FIELD = "MapperKind.INPUT_OBJECT_FIELD",
    ARGUMENT = "MapperKind.ARGUMENT",
    ENUM_VALUE = "MapperKind.ENUM_VALUE"
}
export interface SchemaMapper {
    [MapperKind.TYPE]?: NamedTypeMapper;
    [MapperKind.SCALAR_TYPE]?: ScalarTypeMapper;
    [MapperKind.ENUM_TYPE]?: EnumTypeMapper;
    [MapperKind.COMPOSITE_TYPE]?: CompositeTypeMapper;
    [MapperKind.OBJECT_TYPE]?: ObjectTypeMapper;
    [MapperKind.INPUT_OBJECT_TYPE]?: InputObjectTypeMapper;
    [MapperKind.ABSTRACT_TYPE]?: AbstractTypeMapper;
    [MapperKind.UNION_TYPE]?: UnionTypeMapper;
    [MapperKind.INTERFACE_TYPE]?: InterfaceTypeMapper;
    [MapperKind.ROOT_OBJECT]?: ObjectTypeMapper;
    [MapperKind.QUERY]?: ObjectTypeMapper;
    [MapperKind.MUTATION]?: ObjectTypeMapper;
    [MapperKind.SUBSCRIPTION]?: ObjectTypeMapper;
    [MapperKind.ENUM_VALUE]?: EnumValueMapper;
    [MapperKind.FIELD]?: GenericFieldMapper<GraphQLFieldConfig<any, any> | GraphQLInputFieldConfig>;
    [MapperKind.OBJECT_FIELD]?: FieldMapper;
    [MapperKind.ROOT_FIELD]?: FieldMapper;
    [MapperKind.QUERY_ROOT_FIELD]?: FieldMapper;
    [MapperKind.MUTATION_ROOT_FIELD]?: FieldMapper;
    [MapperKind.SUBSCRIPTION_ROOT_FIELD]?: FieldMapper;
    [MapperKind.INTERFACE_FIELD]?: FieldMapper;
    [MapperKind.COMPOSITE_FIELD]?: FieldMapper;
    [MapperKind.ARGUMENT]?: ArgumentMapper;
    [MapperKind.INPUT_OBJECT_FIELD]?: InputFieldMapper;
    [MapperKind.DIRECTIVE]?: DirectiveMapper;
}
export declare type NamedTypeMapper = (type: GraphQLNamedType, schema: GraphQLSchema) => GraphQLNamedType | null | undefined;
export declare type ScalarTypeMapper = (type: GraphQLScalarType, schema: GraphQLSchema) => GraphQLScalarType | null | undefined;
export declare type EnumTypeMapper = (type: GraphQLEnumType, schema: GraphQLSchema) => GraphQLEnumType | null | undefined;
export declare type EnumValueMapper = (valueConfig: GraphQLEnumValueConfig, typeName: string, schema: GraphQLSchema, externalValue: string) => GraphQLEnumValueConfig | [string, GraphQLEnumValueConfig] | null | undefined;
export declare type CompositeTypeMapper = (type: GraphQLObjectType | GraphQLInterfaceType | GraphQLUnionType, schema: GraphQLSchema) => GraphQLObjectType | GraphQLInterfaceType | GraphQLUnionType | null | undefined;
export declare type ObjectTypeMapper = (type: GraphQLObjectType, schema: GraphQLSchema) => GraphQLObjectType | null | undefined;
export declare type InputObjectTypeMapper = (type: GraphQLInputObjectType, schema: GraphQLSchema) => GraphQLInputObjectType | null | undefined;
export declare type AbstractTypeMapper = (type: GraphQLInterfaceType | GraphQLUnionType, schema: GraphQLSchema) => GraphQLInterfaceType | GraphQLUnionType | null | undefined;
export declare type UnionTypeMapper = (type: GraphQLUnionType, schema: GraphQLSchema) => GraphQLUnionType | null | undefined;
export declare type InterfaceTypeMapper = (type: GraphQLInterfaceType, schema: GraphQLSchema) => GraphQLInterfaceType | null | undefined;
export declare type DirectiveMapper = (directive: GraphQLDirective, schema: GraphQLSchema) => GraphQLDirective | null | undefined;
export declare type GenericFieldMapper<F extends GraphQLFieldConfig<any, any> | GraphQLInputFieldConfig> = (fieldConfig: F, fieldName: string, typeName: string, schema: GraphQLSchema) => F | [string, F] | null | undefined;
export declare type FieldMapper = GenericFieldMapper<GraphQLFieldConfig<any, any>>;
export declare type ArgumentMapper = (argumentConfig: GraphQLArgumentConfig, fieldName: string, typeName: string, schema: GraphQLSchema) => GraphQLArgumentConfig | [string, GraphQLArgumentConfig] | null | undefined;
export declare type InputFieldMapper = GenericFieldMapper<GraphQLInputFieldConfig>;
