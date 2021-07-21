import { DocumentNode } from 'graphql';
import { Operation } from '../types';
export interface FetchBody {
    query?: string;
    operationName: string | undefined;
    variables: undefined | Record<string, any>;
    extensions: undefined | Record<string, any>;
}
export declare const makeFetchBody: (request: {
    query: DocumentNode;
    variables?: object;
}) => FetchBody;
export declare const makeFetchURL: (operation: Operation, body?: FetchBody | undefined) => string;
export declare const makeFetchOptions: (operation: Operation, body?: FetchBody | undefined) => RequestInit;
