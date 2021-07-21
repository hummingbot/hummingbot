import { Source, SingleFileOptions, Loader } from '@graphql-tools/utils';
export declare type LoadTypedefsOptions<ExtraConfig = {
    [key: string]: any;
}> = SingleFileOptions & ExtraConfig & {
    cache?: {
        [key: string]: Source;
    };
    loaders: Loader[];
    filterKinds?: string[];
    ignore?: string | string[];
    sort?: boolean;
};
export declare type UnnormalizedTypeDefPointer = {
    [key: string]: any;
} | string;
/**
 * Asynchronously loads any GraphQL documents (i.e. executable documents like
 * operations and fragments as well as type system definitions) from the
 * provided pointers.
 * @param pointerOrPointers Pointers to the sources to load the documents from
 * @param options Additional options
 */
export declare function loadTypedefs<AdditionalConfig = Record<string, unknown>>(pointerOrPointers: UnnormalizedTypeDefPointer | UnnormalizedTypeDefPointer[], options: LoadTypedefsOptions<Partial<AdditionalConfig>>): Promise<Source[]>;
/**
 * Synchronously loads any GraphQL documents (i.e. executable documents like
 * operations and fragments as well as type system definitions) from the
 * provided pointers.
 * @param pointerOrPointers Pointers to the sources to load the documents from
 * @param options Additional options
 */
export declare function loadTypedefsSync<AdditionalConfig = Record<string, unknown>>(pointerOrPointers: UnnormalizedTypeDefPointer | UnnormalizedTypeDefPointer[], options: LoadTypedefsOptions<Partial<AdditionalConfig>>): Source[];
