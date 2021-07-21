declare const useSetState: <T extends object>(initialState?: T) => [T, (patch: Partial<T> | ((prevState: T) => Partial<T>)) => void];
export default useSetState;
