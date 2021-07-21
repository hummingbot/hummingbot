import { GraphQLEnumType, GraphQLInputType, GraphQLScalarType } from 'graphql';
declare type InputValueTransformer = (type: GraphQLEnumType | GraphQLScalarType, originalValue: any) => any;
export declare function transformInputValue(type: GraphQLInputType, value: any, transformer: InputValueTransformer): any;
export declare function serializeInputValue(type: GraphQLInputType, value: any): any;
export declare function parseInputValue(type: GraphQLInputType, value: any): any;
export declare function parseInputValueLiteral(type: GraphQLInputType, value: any): any;
export {};
