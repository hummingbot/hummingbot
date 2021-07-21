import { DocumentNode, GraphQLSchema, BuildSchemaOptions } from 'graphql';
import { GraphQLSchemaValidationOptions } from 'graphql/type/schema';
import { ExtendedParseOptions } from './parse-graphql-sdl';
export interface Source {
    document?: DocumentNode;
    schema?: GraphQLSchema;
    rawSDL?: string;
    location?: string;
}
export declare type SingleFileOptions = ExtendedParseOptions & GraphQLSchemaValidationOptions & BuildSchemaOptions & {
    cwd?: string;
};
export declare type WithList<T> = T | T[];
export declare type ElementOf<TList> = TList extends Array<infer TElement> ? TElement : never;
export declare type SchemaPointer = WithList<string>;
export declare type SchemaPointerSingle = ElementOf<SchemaPointer>;
export declare type DocumentGlobPathPointer = string;
export declare type DocumentPointer = WithList<DocumentGlobPathPointer>;
export declare type DocumentPointerSingle = ElementOf<DocumentPointer>;
export interface Loader<TPointer = string, TOptions extends SingleFileOptions = SingleFileOptions> {
    loaderId(): string;
    canLoad(pointer: TPointer, options?: TOptions): Promise<boolean>;
    canLoadSync?(pointer: TPointer, options?: TOptions): boolean;
    load(pointer: TPointer, options?: TOptions): Promise<Source | never>;
    loadSync?(pointer: TPointer, options?: TOptions): Source | never;
}
export declare type SchemaLoader<TOptions extends SingleFileOptions = SingleFileOptions> = Loader<SchemaPointerSingle, TOptions>;
export declare type DocumentLoader<TOptions extends SingleFileOptions = SingleFileOptions> = Loader<DocumentPointerSingle, TOptions>;
export declare type UniversalLoader<TOptions extends SingleFileOptions = SingleFileOptions> = Loader<SchemaPointerSingle | DocumentPointerSingle, TOptions>;
