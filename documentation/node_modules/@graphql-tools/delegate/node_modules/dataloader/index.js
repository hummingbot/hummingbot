"use strict";

/**
 * Copyright (c) 2019-present, GraphQL Foundation
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 * 
 */
// A Function, which when given an Array of keys, returns a Promise of an Array
// of values or Errors.
// Optionally turn off batching or caching or provide a cache key function or a
// custom cache instance.
// If a custom cache is provided, it must be of this type (a subset of ES6 Map).

/**
 * A `DataLoader` creates a public API for loading data from a particular
 * data back-end with unique keys such as the `id` column of a SQL table or
 * document name in a MongoDB database, given a batch loading function.
 *
 * Each `DataLoader` instance contains a unique memoized cache. Use caution when
 * used in long-lived applications or those which serve many users with
 * different access permissions and consider creating a new instance per
 * web request.
 */
var DataLoader =
/*#__PURE__*/
function () {
  function DataLoader(batchLoadFn, options) {
    if (typeof batchLoadFn !== 'function') {
      throw new TypeError('DataLoader must be constructed with a function which accepts ' + ("Array<key> and returns Promise<Array<value>>, but got: " + batchLoadFn + "."));
    }

    this._batchLoadFn = batchLoadFn;
    this._maxBatchSize = getValidMaxBatchSize(options);
    this._batchScheduleFn = getValidBatchScheduleFn(options);
    this._cacheKeyFn = getValidCacheKeyFn(options);
    this._cacheMap = getValidCacheMap(options);
    this._batch = null;
  } // Private


  var _proto = DataLoader.prototype;

  /**
   * Loads a key, returning a `Promise` for the value represented by that key.
   */
  _proto.load = function load(key) {
    if (key === null || key === undefined) {
      throw new TypeError('The loader.load() function must be called with a value,' + ("but got: " + String(key) + "."));
    }

    var batch = getCurrentBatch(this);
    var cacheMap = this._cacheMap;

    var cacheKey = this._cacheKeyFn(key); // If caching and there is a cache-hit, return cached Promise.


    if (cacheMap) {
      var cachedPromise = cacheMap.get(cacheKey);

      if (cachedPromise) {
        var cacheHits = batch.cacheHits || (batch.cacheHits = []);
        return new Promise(function (resolve) {
          cacheHits.push(function () {
            return resolve(cachedPromise);
          });
        });
      }
    } // Otherwise, produce a new Promise for this key, and enqueue it to be
    // dispatched along with the current batch.


    batch.keys.push(key);
    var promise = new Promise(function (resolve, reject) {
      batch.callbacks.push({
        resolve: resolve,
        reject: reject
      });
    }); // If caching, cache this promise.

    if (cacheMap) {
      cacheMap.set(cacheKey, promise);
    }

    return promise;
  }
  /**
   * Loads multiple keys, promising an array of values:
   *
   *     var [ a, b ] = await myLoader.loadMany([ 'a', 'b' ]);
   *
   * This is similar to the more verbose:
   *
   *     var [ a, b ] = await Promise.all([
   *       myLoader.load('a'),
   *       myLoader.load('b')
   *     ]);
   *
   * However it is different in the case where any load fails. Where
   * Promise.all() would reject, loadMany() always resolves, however each result
   * is either a value or an Error instance.
   *
   *     var [ a, b, c ] = await myLoader.loadMany([ 'a', 'b', 'badkey' ]);
   *     // c instanceof Error
   *
   */
  ;

  _proto.loadMany = function loadMany(keys) {
    if (!isArrayLike(keys)) {
      throw new TypeError('The loader.loadMany() function must be called with Array<key> ' + ("but got: " + keys + "."));
    } // Support ArrayLike by using only minimal property access


    var loadPromises = [];

    for (var i = 0; i < keys.length; i++) {
      loadPromises.push(this.load(keys[i])["catch"](function (error) {
        return error;
      }));
    }

    return Promise.all(loadPromises);
  }
  /**
   * Clears the value at `key` from the cache, if it exists. Returns itself for
   * method chaining.
   */
  ;

  _proto.clear = function clear(key) {
    var cacheMap = this._cacheMap;

    if (cacheMap) {
      var cacheKey = this._cacheKeyFn(key);

      cacheMap["delete"](cacheKey);
    }

    return this;
  }
  /**
   * Clears the entire cache. To be used when some event results in unknown
   * invalidations across this particular `DataLoader`. Returns itself for
   * method chaining.
   */
  ;

  _proto.clearAll = function clearAll() {
    var cacheMap = this._cacheMap;

    if (cacheMap) {
      cacheMap.clear();
    }

    return this;
  }
  /**
   * Adds the provided key and value to the cache. If the key already
   * exists, no change is made. Returns itself for method chaining.
   *
   * To prime the cache with an error at a key, provide an Error instance.
   */
  ;

  _proto.prime = function prime(key, value) {
    var cacheMap = this._cacheMap;

    if (cacheMap) {
      var cacheKey = this._cacheKeyFn(key); // Only add the key if it does not already exist.


      if (cacheMap.get(cacheKey) === undefined) {
        // Cache a rejected promise if the value is an Error, in order to match
        // the behavior of load(key).
        var promise;

        if (value instanceof Error) {
          promise = Promise.reject(value); // Since this is a case where an Error is intentionally being primed
          // for a given key, we want to disable unhandled promise rejection.

          promise["catch"](function () {});
        } else {
          promise = Promise.resolve(value);
        }

        cacheMap.set(cacheKey, promise);
      }
    }

    return this;
  };

  return DataLoader;
}(); // Private: Enqueue a Job to be executed after all "PromiseJobs" Jobs.
//
// ES6 JavaScript uses the concepts Job and JobQueue to schedule work to occur
// after the current execution context has completed:
// http://www.ecma-international.org/ecma-262/6.0/#sec-jobs-and-job-queues
//
// Node.js uses the `process.nextTick` mechanism to implement the concept of a
// Job, maintaining a global FIFO JobQueue for all Jobs, which is flushed after
// the current call stack ends.
//
// When calling `then` on a Promise, it enqueues a Job on a specific
// "PromiseJobs" JobQueue which is flushed in Node as a single Job on the
// global JobQueue.
//
// DataLoader batches all loads which occur in a single frame of execution, but
// should include in the batch all loads which occur during the flushing of the
// "PromiseJobs" JobQueue after that same execution frame.
//
// In order to avoid the DataLoader dispatch Job occuring before "PromiseJobs",
// A Promise Job is created with the sole purpose of enqueuing a global Job,
// ensuring that it always occurs after "PromiseJobs" ends.
//
// Node.js's job queue is unique. Browsers do not have an equivalent mechanism
// for enqueuing a job to be performed after promise microtasks and before the
// next macrotask. For browser environments, a macrotask is used (via
// setImmediate or setTimeout) at a potential performance penalty.


var enqueuePostPromiseJob = typeof process === 'object' && typeof process.nextTick === 'function' ? function (fn) {
  if (!resolvedPromise) {
    resolvedPromise = Promise.resolve();
  }

  resolvedPromise.then(function () {
    return process.nextTick(fn);
  });
} : setImmediate || setTimeout; // Private: cached resolved Promise instance

var resolvedPromise; // Private: Describes a batch of requests

// Private: Either returns the current batch, or creates and schedules a
// dispatch of a new batch for the given loader.
function getCurrentBatch(loader) {
  // If there is an existing batch which has not yet dispatched and is within
  // the limit of the batch size, then return it.
  var existingBatch = loader._batch;

  if (existingBatch !== null && !existingBatch.hasDispatched && existingBatch.keys.length < loader._maxBatchSize && (!existingBatch.cacheHits || existingBatch.cacheHits.length < loader._maxBatchSize)) {
    return existingBatch;
  } // Otherwise, create a new batch for this loader.


  var newBatch = {
    hasDispatched: false,
    keys: [],
    callbacks: []
  }; // Store it on the loader so it may be reused.

  loader._batch = newBatch; // Then schedule a task to dispatch this batch of requests.

  loader._batchScheduleFn(function () {
    return dispatchBatch(loader, newBatch);
  });

  return newBatch;
}

function dispatchBatch(loader, batch) {
  // Mark this batch as having been dispatched.
  batch.hasDispatched = true; // If there's nothing to load, resolve any cache hits and return early.

  if (batch.keys.length === 0) {
    resolveCacheHits(batch);
    return;
  } // Call the provided batchLoadFn for this loader with the batch's keys and
  // with the loader as the `this` context.


  var batchPromise = loader._batchLoadFn(batch.keys); // Assert the expected response from batchLoadFn


  if (!batchPromise || typeof batchPromise.then !== 'function') {
    return failedDispatch(loader, batch, new TypeError('DataLoader must be constructed with a function which accepts ' + 'Array<key> and returns Promise<Array<value>>, but the function did ' + ("not return a Promise: " + String(batchPromise) + ".")));
  } // Await the resolution of the call to batchLoadFn.


  batchPromise.then(function (values) {
    // Assert the expected resolution from batchLoadFn.
    if (!isArrayLike(values)) {
      throw new TypeError('DataLoader must be constructed with a function which accepts ' + 'Array<key> and returns Promise<Array<value>>, but the function did ' + ("not return a Promise of an Array: " + String(values) + "."));
    }

    if (values.length !== batch.keys.length) {
      throw new TypeError('DataLoader must be constructed with a function which accepts ' + 'Array<key> and returns Promise<Array<value>>, but the function did ' + 'not return a Promise of an Array of the same length as the Array ' + 'of keys.' + ("\n\nKeys:\n" + String(batch.keys)) + ("\n\nValues:\n" + String(values)));
    } // Resolve all cache hits in the same micro-task as freshly loaded values.


    resolveCacheHits(batch); // Step through values, resolving or rejecting each Promise in the batch.

    for (var i = 0; i < batch.callbacks.length; i++) {
      var value = values[i];

      if (value instanceof Error) {
        batch.callbacks[i].reject(value);
      } else {
        batch.callbacks[i].resolve(value);
      }
    }
  })["catch"](function (error) {
    return failedDispatch(loader, batch, error);
  });
} // Private: do not cache individual loads if the entire batch dispatch fails,
// but still reject each request so they do not hang.


function failedDispatch(loader, batch, error) {
  // Cache hits are resolved, even though the batch failed.
  resolveCacheHits(batch);

  for (var i = 0; i < batch.keys.length; i++) {
    loader.clear(batch.keys[i]);
    batch.callbacks[i].reject(error);
  }
} // Private: Resolves the Promises for any cache hits in this batch.


function resolveCacheHits(batch) {
  if (batch.cacheHits) {
    for (var i = 0; i < batch.cacheHits.length; i++) {
      batch.cacheHits[i]();
    }
  }
} // Private: given the DataLoader's options, produce a valid max batch size.


function getValidMaxBatchSize(options) {
  var shouldBatch = !options || options.batch !== false;

  if (!shouldBatch) {
    return 1;
  }

  var maxBatchSize = options && options.maxBatchSize;

  if (maxBatchSize === undefined) {
    return Infinity;
  }

  if (typeof maxBatchSize !== 'number' || maxBatchSize < 1) {
    throw new TypeError("maxBatchSize must be a positive number: " + maxBatchSize);
  }

  return maxBatchSize;
} // Private


function getValidBatchScheduleFn(options) {
  var batchScheduleFn = options && options.batchScheduleFn;

  if (batchScheduleFn === undefined) {
    return enqueuePostPromiseJob;
  }

  if (typeof batchScheduleFn !== 'function') {
    throw new TypeError("batchScheduleFn must be a function: " + batchScheduleFn);
  }

  return batchScheduleFn;
} // Private: given the DataLoader's options, produce a cache key function.


function getValidCacheKeyFn(options) {
  var cacheKeyFn = options && options.cacheKeyFn;

  if (cacheKeyFn === undefined) {
    return function (key) {
      return key;
    };
  }

  if (typeof cacheKeyFn !== 'function') {
    throw new TypeError("cacheKeyFn must be a function: " + cacheKeyFn);
  }

  return cacheKeyFn;
} // Private: given the DataLoader's options, produce a CacheMap to be used.


function getValidCacheMap(options) {
  var shouldCache = !options || options.cache !== false;

  if (!shouldCache) {
    return null;
  }

  var cacheMap = options && options.cacheMap;

  if (cacheMap === undefined) {
    return new Map();
  }

  if (cacheMap !== null) {
    var cacheFunctions = ['get', 'set', 'delete', 'clear'];
    var missingFunctions = cacheFunctions.filter(function (fnName) {
      return cacheMap && typeof cacheMap[fnName] !== 'function';
    });

    if (missingFunctions.length !== 0) {
      throw new TypeError('Custom cacheMap missing methods: ' + missingFunctions.join(', '));
    }
  }

  return cacheMap;
} // Private


function isArrayLike(x) {
  return typeof x === 'object' && x !== null && typeof x.length === 'number' && (x.length === 0 || x.length > 0 && Object.prototype.hasOwnProperty.call(x, x.length - 1));
}

module.exports = DataLoader;