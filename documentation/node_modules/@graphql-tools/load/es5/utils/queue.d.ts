export declare function useQueue<T>(options?: {
    concurrency?: number;
}): {
    add(fn: () => Promise<T>): void;
    runAll(): Promise<T[]>;
};
export declare function useSyncQueue<T>(): {
    add(fn: () => T): void;
    runAll(): void;
};
