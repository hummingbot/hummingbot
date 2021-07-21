declare type MettHandler<EventName, Payload> = (e: Payload, eventName: EventName) => void;
export interface IMett {
    on(eventName: EventName, callback: MettHandler<EventName, Payload>): void;
    off(eventName: EventName, callback: MettHandler<EventName, Payload>): void;
    emit(eventName: EventName, e: Payload): void;
}
declare type EventName = string;
declare type Payload = any;
export declare function mett(): IMett;
export {};
