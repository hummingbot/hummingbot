export declare class InMemoryConfigStore {
    config: Record<string, unknown>;
    path: string;
    constructor();
    createBaseConfig(): Record<string, unknown>;
    get(key: string): unknown;
    set(key: string, value: any): void;
    all(): Record<string, unknown>;
    size(): number;
    has(key: string): boolean;
    delete(key: string): void;
    clear(): void;
}
