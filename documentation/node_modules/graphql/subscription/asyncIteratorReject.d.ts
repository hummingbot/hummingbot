/**
 * Given an error, returns an AsyncIterable which will fail with that error.
 *
 * Similar to Promise.reject(error)
 */
export default function asyncIteratorReject(error: Error): AsyncIterator<void>;
