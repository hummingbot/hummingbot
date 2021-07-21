import { GraphQLSchema, GraphQLField, GraphQLInputField, GraphQLObjectType, GraphQLInputObjectType, GraphQLUnionType, GraphQLScalarType, GraphQLArgument, GraphQLEnumType, GraphQLEnumValue, GraphQLInterfaceType } from 'graphql';
export declare type ExtensionsObject = Record<string, any>;
export declare type ObjectTypeExtensions = {
    type: 'object';
    fields: Record<string, {
        extensions: ExtensionsObject;
        arguments: Record<string, ExtensionsObject>;
    }>;
};
export declare type InputTypeExtensions = {
    type: 'input';
    fields: Record<string, {
        extensions: ExtensionsObject;
    }>;
};
export declare type InterfaceTypeExtensions = {
    type: 'interface';
    fields: Record<string, {
        extensions: ExtensionsObject;
        arguments: Record<string, ExtensionsObject>;
    }>;
};
export declare type UnionTypeExtensions = {
    type: 'union';
};
export declare type ScalarTypeExtensions = {
    type: 'scalar';
};
export declare type EnumTypeExtensions = {
    type: 'enum';
    values: Record<string, ExtensionsObject>;
};
export declare type PossibleTypeExtensions = InputTypeExtensions | InterfaceTypeExtensions | ObjectTypeExtensions | UnionTypeExtensions | ScalarTypeExtensions | EnumTypeExtensions;
export declare type SchemaExtensions = {
    schemaExtensions: ExtensionsObject;
    types: Record<string, {
        extensions: ExtensionsObject;
    } & PossibleTypeExtensions>;
};
export declare function travelSchemaPossibleExtensions(schema: GraphQLSchema, hooks: {
    onSchema: (schema: GraphQLSchema) => any;
    onObjectType: (type: GraphQLObjectType) => any;
    onObjectField: (type: GraphQLObjectType, field: GraphQLField<any, any>) => any;
    onObjectFieldArg: (type: GraphQLObjectType, field: GraphQLField<any, any>, arg: GraphQLArgument) => any;
    onInterface: (type: GraphQLInterfaceType) => any;
    onInterfaceField: (type: GraphQLInterfaceType, field: GraphQLField<any, any>) => any;
    onInterfaceFieldArg: (type: GraphQLInterfaceType, field: GraphQLField<any, any>, arg: GraphQLArgument) => any;
    onInputType: (type: GraphQLInputObjectType) => any;
    onInputFieldType: (type: GraphQLInputObjectType, field: GraphQLInputField) => any;
    onUnion: (type: GraphQLUnionType) => any;
    onScalar: (type: GraphQLScalarType) => any;
    onEnum: (type: GraphQLEnumType) => any;
    onEnumValue: (type: GraphQLEnumType, value: GraphQLEnumValue) => any;
}): void;
export declare function mergeExtensions(extensions: SchemaExtensions[]): SchemaExtensions;
export declare function applyExtensions(schema: GraphQLSchema, extensions: SchemaExtensions): GraphQLSchema;
export declare function extractExtensionsFromSchema(schema: GraphQLSchema): SchemaExtensions;
