import { GraphQLList, GraphQLSchema, GraphQLError, GraphQLResolveInfo } from 'graphql';
import { SubschemaConfig } from '../types';
export declare function handleList(type: GraphQLList<any>, list: Array<any>, errors: ReadonlyArray<GraphQLError>, subschema: GraphQLSchema | SubschemaConfig, context: Record<string, any>, info: GraphQLResolveInfo, skipTypeMerging?: boolean): any[];
