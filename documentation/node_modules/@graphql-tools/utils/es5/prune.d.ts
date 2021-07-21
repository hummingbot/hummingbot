import { GraphQLSchema } from 'graphql';
/**
 * Options for removing unused types from the schema
 */
export interface PruneSchemaOptions {
    /**
     * Set to `true` to skip pruning object types or interfaces with no no fields
     */
    skipEmptyCompositeTypePruning?: boolean;
    /**
     * Set to `true` to skip pruning interfaces that are not implemented by any
     * other types
     */
    skipUnimplementedInterfacesPruning?: boolean;
    /**
     * Set to `true` to skip pruning empty unions
     */
    skipEmptyUnionPruning?: boolean;
    /**
     * Set to `true` to skip pruning unused types
     */
    skipUnusedTypesPruning?: boolean;
}
/**
 * Prunes the provided schema, removing unused and empty types
 * @param schema The schema to prune
 * @param options Additional options for removing unused types from the schema
 */
export declare function pruneSchema(schema: GraphQLSchema, options?: PruneSchemaOptions): GraphQLSchema;
