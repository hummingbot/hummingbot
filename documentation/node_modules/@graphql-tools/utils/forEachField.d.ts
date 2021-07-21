import { GraphQLSchema } from 'graphql';
import { IFieldIteratorFn } from './Interfaces';
export declare function forEachField(schema: GraphQLSchema, fn: IFieldIteratorFn): void;
