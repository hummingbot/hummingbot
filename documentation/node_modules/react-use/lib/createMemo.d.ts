declare const createMemo: <T extends (...args: any) => any>(fn: T) => (...args: Parameters<T>) => ReturnType<T>;
export default createMemo;
