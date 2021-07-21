import { UseEventTarget } from './useEvent';
export declare type KeyPredicate = (event: KeyboardEvent) => boolean;
export declare type KeyFilter = null | undefined | string | ((event: KeyboardEvent) => boolean);
export declare type Handler = (event: KeyboardEvent) => void;
export interface UseKeyOptions {
    event?: 'keydown' | 'keypress' | 'keyup';
    target?: UseEventTarget;
    options?: any;
}
declare const useKey: (key: KeyFilter, fn?: Handler, opts?: UseKeyOptions, deps?: readonly any[]) => void;
export default useKey;
