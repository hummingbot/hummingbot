import { ExecutionResult } from 'graphql';
/**
 * Split and transform result of the query produced by the `merge` function
 */
export declare function splitResult(mergedResult: ExecutionResult, numResults: number): Array<ExecutionResult>;
