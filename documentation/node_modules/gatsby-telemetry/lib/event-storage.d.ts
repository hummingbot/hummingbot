import Configstore from "configstore";
import { Store } from "./store";
import { InMemoryConfigStore } from "./in-memory-store";
export declare class EventStorage {
    analyticsApi: string;
    config: Configstore | InMemoryConfigStore;
    store: Store;
    verbose: boolean;
    debugEvents: boolean;
    disabled: boolean;
    constructor();
    isTrackingDisabled(): boolean;
    addEvent(event: unknown): void;
    sendEvents(): Promise<boolean>;
    submitEvents(events: unknown): Promise<boolean>;
    getUserAgent(): string;
    getConfig(key: string): string | boolean | Record<string, unknown>;
    updateConfig(key: string, value: string | number | boolean | null): void;
}
