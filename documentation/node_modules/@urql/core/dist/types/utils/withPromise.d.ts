import { Source } from 'wonka';
import { PromisifiedSource } from '../types';
export declare function withPromise<T>(source$: Source<T>): PromisifiedSource<T>;
