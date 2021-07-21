import { GraphQLSchema, GraphQLObjectType } from 'graphql';
/**
 * Get all GraphQL types from schema without:
 *
 * - Query, Mutation, Subscription objects
 * - Internal scalars added by parser
 *
 * @param schema
 */
export declare function getUserTypesFromSchema(schema: GraphQLSchema): GraphQLObjectType[];
