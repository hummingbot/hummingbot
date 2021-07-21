import { GraphQLSchema } from 'graphql';
import { Transform } from '@graphql-tools/utils';
import { SubschemaConfig } from '@graphql-tools/delegate';
export declare function wrapSchema(subschemaOrSubschemaConfig: GraphQLSchema | SubschemaConfig, transforms?: Array<Transform>): GraphQLSchema;
