import web3 from 'web3';
import { default as constants } from './../../chains/solana/solana.constants';

/**
 *
 * @param value
 * @param errorMessage
 */
export const getNotNullOrThrowError = <R>(
  value?: any,
  errorMessage: string = 'Value is null or undefined'
): R => {
  if (value === undefined || value === null) throw new Error(errorMessage);

  return value as R;
};

/**
 *
 * @param milliseconds
 */
export const sleep = (milliseconds: number) =>
  new Promise((callback) => setTimeout(callback, milliseconds));

/**
 * Same as Promise.all(items.map(item => task(item))), but it waits for
 * the first {batchSize} promises to finish before starting the next batch.
 *
 * @template A
 * @template B
 * @param {function(A): B} task The task to run for each item.
 * @param {A[]} items Arguments to pass to the task for each call.
 * @param {int} batchSize The number of items to process at a time.
 * @param {int} delayBetweenBatches Delay between each batch (milliseconds).
 * @returns {B[]}
 */
export const promiseAllInBatches = async <I, O>(
  task: (item: I) => O,
  items: any[],
  batchSize: number = constants.parallel.all.batchSize,
  delayBetweenBatches: number = constants.parallel.all.delayBetweenBatches
): Promise<O[]> => {
  let position = 0;
  let results: any[] = [];

  if (!batchSize) {
    batchSize = items.length;
  }

  while (position < items.length) {
    const itemsForBatch = items.slice(position, position + batchSize);
    results = [
      ...results,
      ...(await Promise.all(itemsForBatch.map((item) => task(item)))),
    ];
    position += batchSize;

    if (position < items.length) {
      if (delayBetweenBatches > 0) {
        await sleep(delayBetweenBatches);
      }
    }
  }

  return results;
};

/**
 *
 */
export const getRandonBN = () => {
  return web3.utils.toBN(web3.utils.randomHex(32));
};

/**
 * @param targetObject
 * @param targetFunction
 * @param targetParameters
 * @param maxNumberOfRetries 0 means no retries
 * @param delayBetweenRetries 0 means no delay (milliseconds)
 * @param timeout 0 means no timeout (milliseconds)
 * @param timeoutMessage
 */
export const runWithRetryAndTimeout = async <R>(
  targetObject: any,
  targetFunction: (...args: any[]) => R,
  targetParameters: any,
  maxNumberOfRetries: number = constants.retry.all.maxNumberOfRetries,
  delayBetweenRetries: number = constants.retry.all.delayBetweenRetries,
  timeout: number = constants.timeout.all,
  timeoutMessage: string = 'Timeout exceeded.'
): Promise<R> => {
  let retryCount = 0;
  let timer: any;

  if (timeout > 0) {
    timer = setTimeout(() => new Error(timeoutMessage), timeout);
  }

  do {
    try {
      const result = await targetFunction.apply(targetObject, targetParameters);

      if (timeout > 0) {
        clearTimeout(timer);
      }

      return result as R;
    } catch (error) {
      retryCount++;
      if (retryCount < maxNumberOfRetries) {
        if (delayBetweenRetries > 0) {
          await sleep(delayBetweenRetries);
        }
      } else {
        throw error;
      }
    }
  } while (retryCount < maxNumberOfRetries);

  throw Error('Unknown error.');
};
