import { GraphQLFieldResolver, GraphQLSchema } from 'graphql';
import { IMakeRemoteExecutableSchemaOptions } from './types';
import { Executor, Subscriber } from '@graphql-tools/delegate';
export declare function makeRemoteExecutableSchema({ schema: schemaOrTypeDefs, executor, subscriber, createResolver, buildSchemaOptions, }: IMakeRemoteExecutableSchemaOptions): GraphQLSchema;
export declare function defaultCreateRemoteResolver(executor: Executor, subscriber: Subscriber): GraphQLFieldResolver<any, any>;
