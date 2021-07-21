import { GraphQLSchema } from 'graphql';
import { ILogger } from './types';
export declare function addErrorLoggingToSchema(schema: GraphQLSchema, logger?: ILogger): GraphQLSchema;
