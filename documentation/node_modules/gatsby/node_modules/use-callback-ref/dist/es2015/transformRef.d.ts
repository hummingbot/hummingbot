import { ReactRef, RefObject } from './types';
export declare function transformRef<T, K>(ref: ReactRef<K>, transformer: (original: T) => K): RefObject<T>;
