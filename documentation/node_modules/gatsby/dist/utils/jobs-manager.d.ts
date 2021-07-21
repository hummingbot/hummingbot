interface IBaseJob {
    name: string;
    outputDir: string;
    args: Record<string, any>;
}
interface IJobInput {
    inputPaths: Array<string>;
    plugin: {
        name: string;
        version: string;
        resolve: string;
    };
}
interface IInternalJob {
    id: string;
    contentDigest: string;
    inputPaths: Array<{
        path: string;
        contentDigest: string;
    }>;
    plugin: {
        name: string;
        version: string;
        resolve: string;
        isLocal: boolean;
    };
}
export declare type JobResultInterface = Record<string, unknown>;
export declare type JobInput = IBaseJob & IJobInput;
export declare type InternalJob = IBaseJob & IInternalJob;
export declare class WorkerError extends Error {
    constructor(error: Error | string);
}
/**
 * Create an internal job object
 */
export declare function createInternalJob(job: JobInput | InternalJob, plugin: {
    name: string;
    version: string;
    resolve: string;
}): InternalJob;
/**
 * Creates a job
 */
export declare function enqueueJob(job: InternalJob): Promise<object>;
/**
 * Get in progress job promise
 */
export declare function getInProcessJobPromise(contentDigest: string): Promise<object> | undefined;
/**
 * Remove a job from our inProgressQueue to reduce memory usage
 */
export declare function removeInProgressJob(contentDigest: string): void;
/**
 * Wait for all processing jobs to have finished
 */
export declare function waitUntilAllJobsComplete(): Promise<void>;
export declare function isJobStale(job: Partial<InternalJob> & {
    inputPaths: InternalJob["inputPaths"];
}): boolean;
export {};
