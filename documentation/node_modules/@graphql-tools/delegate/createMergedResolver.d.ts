import { IFieldResolver } from '@graphql-tools/utils';
export declare function createMergedResolver({ fromPath, dehoist, delimeter, }: {
    fromPath?: Array<string>;
    dehoist?: boolean;
    delimeter?: string;
}): IFieldResolver<any, any>;
