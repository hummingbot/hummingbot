import { GraphQLObjectType } from 'graphql';
export declare function createSchemaDefinition(def: {
    query: string | GraphQLObjectType | null;
    mutation: string | GraphQLObjectType | null;
    subscription: string | GraphQLObjectType | null;
}, config?: {
    force?: boolean;
}): string;
