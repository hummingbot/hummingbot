import { DefinitionNode, DocumentNode, GraphQLSchema, Source } from 'graphql';
declare type Omit<T, K extends keyof any> = Pick<T, Exclude<keyof T, K>>;
declare type CompareFn<T> = (a: T, b: T) => number;
export interface Config {
    /**
     * Produces `schema { query: ..., mutation: ..., subscription: ... }`
     *
     * Default: true
     */
    useSchemaDefinition?: boolean;
    /**
     * Creates schema definition, even when no types are available
     * Produces: `schema { query: Query }`
     *
     * Default: false
     */
    forceSchemaDefinition?: boolean;
    /**
     * Throws an error on a merge conflict
     *
     * Default: false
     */
    throwOnConflict?: boolean;
    /**
     * Descriptions are defined as preceding string literals, however an older
     * experimental version of the SDL supported preceding comments as
     * descriptions. Set to true to enable this deprecated behavior.
     * This option is provided to ease adoption and will be removed in v16.
     *
     * Default: false
     */
    commentDescriptions?: boolean;
    /**
     * Puts the next directive first.
     *
     * Default: false
     *
     * @example:
     * Given:
     * ```graphql
     *  type User { a: String @foo }
     *  type User { a: String @bar }
     * ```
     *
     * Results:
     * ```
     *  type User { a: @bar @foo }
     * ```
     */
    reverseDirectives?: boolean;
    exclusions?: string[];
    sort?: boolean | CompareFn<string>;
    convertExtensions?: boolean;
}
/**
 * Merges multiple type definitions into a single `DocumentNode`
 * @param types The type definitions to be merged
 */
export declare function mergeTypeDefs(types: Array<string | Source | DocumentNode | GraphQLSchema>): DocumentNode;
export declare function mergeTypeDefs(types: Array<string | Source | DocumentNode | GraphQLSchema>, config?: Partial<Config> & {
    commentDescriptions: true;
}): string;
export declare function mergeTypeDefs(types: Array<string | Source | DocumentNode | GraphQLSchema>, config?: Omit<Partial<Config>, 'commentDescriptions'>): DocumentNode;
export declare function mergeGraphQLTypes(types: Array<string | Source | DocumentNode | GraphQLSchema>, config: Config): DefinitionNode[];
export {};
