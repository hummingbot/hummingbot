import { Source, SchemaPointerSingle, DocumentLoader, SingleFileOptions } from '@graphql-tools/utils';
/**
 * Additional options for loading from a JSON file
 */
export interface JsonFileLoaderOptions extends SingleFileOptions {
}
/**
 * This loader loads documents and type definitions from JSON files.
 *
 * The JSON file can be the result of an introspection query made against a schema:
 *
 * ```js
 * const schema = await loadSchema('schema-introspection.json', {
 *   loaders: [
 *     new JsonFileLoader()
 *   ]
 * });
 * ```
 *
 * Or it can be a `DocumentNode` object representing a GraphQL document or type definitions:
 *
 * ```js
 * const documents = await loadDocuments('queries/*.json', {
 *   loaders: [
 *     new GraphQLFileLoader()
 *   ]
 * });
 * ```
 */
export declare class JsonFileLoader implements DocumentLoader {
    loaderId(): string;
    canLoad(pointer: SchemaPointerSingle, options: JsonFileLoaderOptions): Promise<boolean>;
    canLoadSync(pointer: SchemaPointerSingle, options: JsonFileLoaderOptions): boolean;
    load(pointer: SchemaPointerSingle, options: JsonFileLoaderOptions): Promise<Source>;
    loadSync(pointer: SchemaPointerSingle, options: JsonFileLoaderOptions): Source;
}
