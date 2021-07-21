import { GraphQLSchema, GraphQLNamedType, GraphQLField, GraphQLInputField, GraphQLFieldConfig, GraphQLInputFieldConfig, GraphQLSchemaConfig, GraphQLObjectTypeConfig, GraphQLInterfaceTypeConfig, GraphQLUnionTypeConfig, GraphQLScalarTypeConfig, GraphQLEnumTypeConfig, GraphQLInputObjectTypeConfig, GraphQLEnumValue, GraphQLEnumValueConfig } from 'graphql';
export declare type DirectiveUseMap = {
    [key: string]: any;
};
declare type DirectableGraphQLObject = GraphQLSchema | GraphQLSchemaConfig | GraphQLNamedType | GraphQLObjectTypeConfig<any, any> | GraphQLInterfaceTypeConfig<any, any> | GraphQLUnionTypeConfig<any, any> | GraphQLScalarTypeConfig<any, any> | GraphQLEnumTypeConfig | GraphQLEnumValue | GraphQLEnumValueConfig | GraphQLInputObjectTypeConfig | GraphQLField<any, any> | GraphQLInputField | GraphQLFieldConfig<any, any> | GraphQLInputFieldConfig;
export declare function getDirectives(schema: GraphQLSchema, node: DirectableGraphQLObject): DirectiveUseMap;
export {};
