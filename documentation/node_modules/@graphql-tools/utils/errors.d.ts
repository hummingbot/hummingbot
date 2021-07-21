import { GraphQLError } from 'graphql';
export declare const ERROR_SYMBOL: unique symbol;
export declare function relocatedError(originalError: GraphQLError, path?: ReadonlyArray<string | number>): GraphQLError;
export declare function slicedError(originalError: GraphQLError): GraphQLError;
export declare function getErrorsByPathSegment(errors: ReadonlyArray<GraphQLError>): Record<string, Array<GraphQLError>>;
export declare function setErrors(result: any, errors: Array<GraphQLError>): void;
export declare function getErrors(result: any, pathSegment: string): Array<GraphQLError>;
