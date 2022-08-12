import web3 from 'web3';

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
 * @param {int} delayInMilliseconds Delay between each batch.
 * @returns {B[]}
 */
export const promiseAllInBatches = async <I, O>(
  task: (item: I) => O,
  items: any[],
  batchSize: number,
  delayInMilliseconds: number = 0
): Promise<O[]> => {
  let position = 0;
  let results: any[] = [];

  while (position < items.length) {
    const itemsForBatch = items.slice(position, position + batchSize);
    results = [
      ...results,
      ...(await Promise.all(itemsForBatch.map((item) => task(item)))),
    ];
    position += batchSize;

    if (position < items.length) {
      await sleep(delayInMilliseconds);
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
 * @param maxNumberOfRetries
 * @param delayBetweenRetriesInMilliseconds
 * @param timeoutInMilliseconds
 * @param timeoutMessage
 */
export const runWithRetryAndTimeout = async <R>(
  targetObject: any,
  targetFunction: any,
  targetParameters: any,
  maxNumberOfRetries: number = 0, // 0 means no retries
  delayBetweenRetriesInMilliseconds: number = 0, // 0 means no delay
  timeoutInMilliseconds: number = 0, // 0 means no timeout,
  timeoutMessage: string = 'Timeout exceeded.'
): Promise<R> => {
  let retryCount = 0;
  let timer: any;

  if (timeoutInMilliseconds > 0) {
    timer = setTimeout(() => new Error(timeoutMessage), timeoutInMilliseconds);
  }

  do {
    try {
      const result = await targetFunction.apply(targetObject, targetParameters);

      if (timeoutInMilliseconds > 0) {
        clearTimeout(timer);
      }

      return result as R;
    } catch (error) {
      retryCount++;
      if (retryCount < maxNumberOfRetries) {
        if (delayBetweenRetriesInMilliseconds > 0) {
          await sleep(delayBetweenRetriesInMilliseconds);
        }
      } else {
        throw error;
      }
    }
  } while (retryCount < maxNumberOfRetries);

  throw Error('Unknown error.');
};
