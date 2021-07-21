export interface Actions<T extends object> {
    get: <K extends keyof T>(key: K) => T[K];
    set: <K extends keyof T>(key: K, value: T[K]) => void;
    remove: <K extends keyof T>(key: K) => void;
    reset: () => void;
}
declare const useMap: <T extends object = any>(initialMap?: T) => [T, Actions<T>];
export default useMap;
