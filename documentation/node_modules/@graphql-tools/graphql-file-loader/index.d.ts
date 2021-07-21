import { Source, UniversalLoader, DocumentPointerSingle, SchemaPointerSingle, SingleFileOptions } from '@graphql-tools/utils';
/**
 * Additional options for loading from a GraphQL file
 */
export interface GraphQLFileLoaderOptions extends SingleFileOptions {
    /**
     * Set to `true` to disable handling `#import` syntax
     */
    skipGraphQLImport?: boolean;
}
/**
 * This loader loads documents and type definitions from `.graphql` files.
 *
 * You can load a single source:
 *
 * ```js
 * const schema = await loadSchema('schema.graphql', {
 *   loaders: [
 *     new GraphQLFileLoader()
 *   ]
 * });
 * ```
 *
 * Or provide a glob pattern to load multiple sources:
 *
 * ```js
 * const schema = await loadSchema('graphql/*.graphql', {
 *   loaders: [
 *     new GraphQLFileLoader()
 *   ]
 * });
 * ```
 */
export declare class GraphQLFileLoader implements UniversalLoader<GraphQLFileLoaderOptions> {
    loaderId(): string;
    canLoad(pointer: SchemaPointerSingle | DocumentPointerSingle, options: GraphQLFileLoaderOptions): Promise<boolean>;
    canLoadSync(pointer: SchemaPointerSingle | DocumentPointerSingle, options: GraphQLFileLoaderOptions): boolean;
    load(pointer: SchemaPointerSingle | DocumentPointerSingle, options: GraphQLFileLoaderOptions): Promise<Source>;
    loadSync(pointer: SchemaPointerSingle | DocumentPointerSingle, options: GraphQLFileLoaderOptions): Source;
    handleFileContent(rawSDL: string, pointer: string, options: GraphQLFileLoaderOptions): {
        location: string;
        document: import("graphql").DocumentNode;
        rawSDL: string;
    } | {
        location: string;
        document: {
            definitions: import("graphql").DefinitionNode[];
            kind: "Document";
            loc?: import("graphql").Location;
        };
    };
}
