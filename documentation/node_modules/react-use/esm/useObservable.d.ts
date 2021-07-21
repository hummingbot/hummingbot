export interface Observable<T> {
    subscribe: (listener: (value: T) => void) => {
        unsubscribe: () => void;
    };
}
declare function useObservable<T>(observable$: Observable<T>): T | undefined;
declare function useObservable<T>(observable$: Observable<T>, initialValue: T): T;
export default useObservable;
