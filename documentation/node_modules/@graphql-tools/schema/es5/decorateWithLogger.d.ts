import { GraphQLFieldResolver } from 'graphql';
import { ILogger } from './types';
export declare function decorateWithLogger(fn: GraphQLFieldResolver<any, any>, logger: ILogger, hint: string): GraphQLFieldResolver<any, any>;
