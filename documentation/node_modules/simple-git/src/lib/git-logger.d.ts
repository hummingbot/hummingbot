import { Debugger } from 'debug';
/**
 * The shared debug logging instance
 */
export declare const log: Debugger;
declare type OutputLoggingHandler = (message: string, ...args: any[]) => void;
export interface OutputLogger extends OutputLoggingHandler {
    readonly key: string;
    readonly label: string;
    debug: OutputLoggingHandler;
    info: OutputLoggingHandler;
    step(nextStep?: string): OutputLogger;
    child(name: string): OutputLogger;
    sibling(name: string): OutputLogger;
    destroy(): void;
}
export declare function createLogger(label: string, verbose?: string | Debugger, initialStep?: string, infoDebugger?: Debugger): OutputLogger;
/**
 * The `GitLogger` is used by the main `SimpleGit` runner to handle logging
 * any warnings or errors.
 */
export declare class GitLogger {
    private _out;
    error: OutputLoggingHandler;
    warn: OutputLoggingHandler;
    constructor(_out?: Debugger);
    silent(silence?: boolean): void;
}
export {};
