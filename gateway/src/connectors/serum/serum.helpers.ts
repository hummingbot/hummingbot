/**
 *
 * @param milliseconds
 */
export const sleep = (milliseconds: number) => new Promise(callback => setTimeout(callback, milliseconds));

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
export const promiseAllInBatches = async <I, O>(task: (item: I) => O, items: any[], batchSize: number, delayInMilliseconds: number = 0): Promise<O[]> =>{
    let position = 0;
    let results: any[] = [];

    while (position < items.length) {
        const itemsForBatch = items.slice(position, position + batchSize);
        results = [...results, ...await Promise.all(itemsForBatch.map(item => task(item)))];
        await sleep(delayInMilliseconds);
        position += batchSize;
    }

    return results;
}
