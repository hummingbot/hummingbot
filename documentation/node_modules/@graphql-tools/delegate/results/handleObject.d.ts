import { GraphQLCompositeType, GraphQLError, GraphQLSchema, GraphQLResolveInfo } from 'graphql';
import { SubschemaConfig } from '../types';
export declare function handleObject(type: GraphQLCompositeType, object: any, errors: ReadonlyArray<GraphQLError>, subschema: GraphQLSchema | SubschemaConfig, context: Record<string, any>, info: GraphQLResolveInfo, skipTypeMerging?: boolean): any;
