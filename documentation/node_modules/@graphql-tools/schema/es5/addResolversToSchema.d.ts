import { GraphQLSchema } from 'graphql';
import { IResolvers, IResolverValidationOptions, IAddResolversToSchemaOptions } from '@graphql-tools/utils';
export declare function addResolversToSchema(schemaOrOptions: GraphQLSchema | IAddResolversToSchemaOptions, legacyInputResolvers?: IResolvers, legacyInputValidationOptions?: IResolverValidationOptions): GraphQLSchema;
