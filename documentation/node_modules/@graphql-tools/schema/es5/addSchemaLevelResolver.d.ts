import { GraphQLSchema, GraphQLFieldResolver } from 'graphql';
export declare function addSchemaLevelResolver(schema: GraphQLSchema, fn: GraphQLFieldResolver<any, any>): GraphQLSchema;
