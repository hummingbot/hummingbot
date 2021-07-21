/// <reference types="node" />
import { EventEmitter } from 'events';
import { PubSubEngine } from './pubsub-engine';
export interface PubSubOptions {
    eventEmitter?: EventEmitter;
}
export declare class PubSub extends PubSubEngine {
    protected ee: EventEmitter;
    private subscriptions;
    private subIdCounter;
    constructor(options?: PubSubOptions);
    publish(triggerName: string, payload: any): Promise<void>;
    subscribe(triggerName: string, onMessage: (...args: any[]) => void): Promise<number>;
    unsubscribe(subId: number): void;
}
