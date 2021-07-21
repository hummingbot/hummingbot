declare const useThrottleFn: <T>(fn: (...args: any[]) => T, ms: number | undefined, args: any[]) => T;
export default useThrottleFn;
