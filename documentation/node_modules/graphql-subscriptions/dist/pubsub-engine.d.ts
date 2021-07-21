export declare abstract class PubSubEngine {
    abstract publish(triggerName: string, payload: any): Promise<void>;
    abstract subscribe(triggerName: string, onMessage: Function, options: Object): Promise<number>;
    abstract unsubscribe(subId: number): any;
    asyncIterator<T>(triggers: string | string[]): AsyncIterator<T>;
}
