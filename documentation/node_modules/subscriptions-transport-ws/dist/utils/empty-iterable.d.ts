import { $$asyncIterator } from 'iterall';
declare type EmptyIterable = AsyncIterator<any> & {
    [$$asyncIterator]: any;
};
export declare const createEmptyIterable: () => EmptyIterable;
export {};
