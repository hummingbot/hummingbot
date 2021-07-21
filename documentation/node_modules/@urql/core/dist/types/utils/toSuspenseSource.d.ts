import { Source } from 'wonka';
/** This converts a Source to a suspense Source; It will forward the first result synchronously or throw a promise that resolves when the result becomes available */
export declare const toSuspenseSource: <T>(source: Source<T>) => Source<T>;
