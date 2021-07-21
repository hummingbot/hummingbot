declare type ScheduleCompleteCallback = () => void;
export declare class Scheduler {
    private concurrency;
    private pending;
    private running;
    constructor(concurrency?: number);
    private schedule;
    next(): Promise<ScheduleCompleteCallback>;
}
export {};
