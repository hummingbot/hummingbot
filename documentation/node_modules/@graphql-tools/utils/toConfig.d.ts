import { GraphQLArgument, GraphQLFieldConfigArgumentMap, GraphQLField, GraphQLInputField, GraphQLInputFieldConfig, GraphQLArgumentConfig, GraphQLFieldConfig } from 'graphql';
export declare function inputFieldToFieldConfig(field: GraphQLInputField): GraphQLInputFieldConfig;
export declare function fieldToFieldConfig(field: GraphQLField<any, any>): GraphQLFieldConfig<any, any>;
export declare function argsToFieldConfigArgumentMap(args: ReadonlyArray<GraphQLArgument>): GraphQLFieldConfigArgumentMap;
export declare function argumentToArgumentConfig(arg: GraphQLArgument): GraphQLArgumentConfig;
