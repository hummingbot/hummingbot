export declare type UsePromise = () => <T>(promise: Promise<T>) => Promise<T>;
declare const usePromise: UsePromise;
export default usePromise;
