import { Source } from '@graphql-tools/utils';
declare type AddValidSource = (source: Source) => void;
declare type ParseOptions = {
    partialSource: Partial<Source>;
    options: any;
    globOptions: any;
    pointerOptionMap: any;
    addValidSource: AddValidSource;
};
export declare function parseSource({ partialSource, options, globOptions, pointerOptionMap, addValidSource }: ParseOptions): void;
export {};
