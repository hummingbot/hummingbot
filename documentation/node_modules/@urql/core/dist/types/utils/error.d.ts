import { GraphQLError } from 'graphql';
/** An error which can consist of GraphQL errors and Network errors. */
export declare class CombinedError extends Error {
    name: string;
    message: string;
    graphQLErrors: GraphQLError[];
    networkError?: Error;
    response?: any;
    constructor({ networkError, graphQLErrors, response, }: {
        networkError?: Error;
        graphQLErrors?: Array<string | Partial<GraphQLError> | Error>;
        response?: any;
    });
    toString(): string;
}
