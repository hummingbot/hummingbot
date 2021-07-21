import { GraphQLSchema } from 'graphql';
import { IDefaultValueIteratorFn } from './Interfaces';
export declare function forEachDefaultValue(schema: GraphQLSchema, fn: IDefaultValueIteratorFn): void;
