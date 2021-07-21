import { GraphQLSchema, DocumentNode, BuildSchemaOptions } from 'graphql';
import { ILogger } from '@graphql-tools/schema';
import { Config } from './typedefs-mergers/merge-typedefs';
import { IResolvers, SchemaDirectiveVisitor, IResolverValidationOptions } from '@graphql-tools/utils';
/**
 * Configuration object for schema merging
 */
export interface MergeSchemasConfig<Resolvers extends IResolvers = IResolvers> extends Config, BuildSchemaOptions {
    /**
     * The schemas to be merged
     */
    schemas: GraphQLSchema[];
    /**
     * Additional type definitions to also merge
     */
    typeDefs?: (DocumentNode | string)[] | DocumentNode | string;
    /**
     * Additional resolvers to also merge
     */
    resolvers?: Resolvers | Resolvers[];
    /**
     * Schema directives to apply to the type definitions being merged, if provided
     */
    schemaDirectives?: {
        [directiveName: string]: typeof SchemaDirectiveVisitor;
    };
    /**
     * Options to validate the resolvers being merged, if provided
     */
    resolverValidationOptions?: IResolverValidationOptions;
    /**
     * Custom logger instance
     */
    logger?: ILogger;
}
/**
 * Synchronously merges multiple schemas, typeDefinitions and/or resolvers into a single schema.
 * @param config Configuration object
 */
export declare function mergeSchemas(config: MergeSchemasConfig): GraphQLSchema;
/**
 * Synchronously merges multiple schemas, typeDefinitions and/or resolvers into a single schema.
 * @param config Configuration object
 */
export declare function mergeSchemasAsync(config: MergeSchemasConfig): Promise<GraphQLSchema>;
