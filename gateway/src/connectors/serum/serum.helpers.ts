import web3 from 'web3';

export const getNotNullOrThrowError = <R>(
  value?: any,
  errorMessage: string = 'Value is null or undefined'
): R => {
  if (!value) throw new Error(errorMessage);

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
    await sleep(delayInMilliseconds);
    position += batchSize;
  }

  return results;
};

export const getRandonBN = () => {
  return web3.utils.toBN(web3.utils.randomHex(32));
};

/* eslint-disable */
/* tslint:disable */
/*
	cycle.js
	2021-05-31

	Public Domain.

	NO WARRANTY EXPRESSED OR IMPLIED. USE AT YOUR OWN RISK.

	This code should be minified before deployment.
	See https://www.crockford.com/jsmin.html

	USE YOUR OWN COPY. IT IS EXTREMELY UNWISE TO LOAD CODE FROM SERVERS YOU DO
	NOT CONTROL.
*/

// The file uses the WeakMap feature of ES6.

/*jslint eval */

/*property
	$ref, decycle, forEach, get, indexOf, isArray, keys, length, push,
	retrocycle, set, stringify, test
*/

// @ts-ignore
if (typeof JSON.decycle !== 'function') {
  // @ts-ignore
  JSON.decycle = function decycle(object, replacer) {
    'use strict';

// Make a deep copy of an object or array, assuring that there is at most
// one instance of each object or array in the resulting structure. The
// duplicate references (which might be forming cycles) are replaced with
// an object of the form

//      {"$ref": PATH}

// where the PATH is a JSONPath string that locates the first occurance.

// So,

//      var a = [];
//      a[0] = a;
//      return JSON.stringify(JSON.decycle(a));

// produces the string '[{"$ref":"$"}]'.

// If a replacer function is provided, then it will be called for each value.
// A replacer function receives a value and returns a replacement value.

// JSONPath is used to locate the unique object. $ indicates the top level of
// the object or array. [NUMBER] or [STRING] indicates a child element or
// property.

    var objects = new WeakMap();     // object to path mappings

    return (function derez(value, path) {

// The derez function recurses through the object, producing the deep copy.

      var old_path;   // The path of an earlier occurance of value
      var nu: any;         // The new object or array

// If a replacer function was provided, then call it to get a replacement value.

      if (replacer !== undefined) {
        value = replacer(value);
      }

// typeof null === "object", so go on if this value is really an object but not
// one of the weird builtin objects.

      if (
        typeof value === 'object'
        && value !== null
        && !(value instanceof Boolean)
        && !(value instanceof Date)
        && !(value instanceof Number)
        && !(value instanceof RegExp)
        && !(value instanceof String)
      ) {

// If the value is an object or array, look to see if we have already
// encountered it. If so, return a {"$ref":PATH} object. This uses an
// ES6 WeakMap.

        old_path = objects.get(value);
        if (old_path !== undefined) {
          return {$ref: old_path};
        }

// Otherwise, accumulate the unique value and its path.

        objects.set(value, path);

// If it is an array, replicate the array.

        if (Array.isArray(value)) {
          nu = [];
          value.forEach(function (element, i) {
            nu[i] = derez(element, path + '[' + i + ']');
          });
        } else {

// If it is an object, replicate the object.

          nu = {};
          Object.keys(value).forEach(function (name) {
            nu[name] = derez(
              value[name],
              path + '[' + JSON.stringify(name) + ']'
            );
          });
        }
        return nu;
      }
      return value;
    }(object, '$'));
  };
}

// @ts-ignore
if (typeof JSON.retrocycle !== 'function') {
  // @ts-ignore
  JSON.retrocycle = function retrocycle($) {
    'use strict';

// Restore an object that was reduced by decycle. Members whose values are
// objects of the form
//      {$ref: PATH}
// are replaced with references to the value found by the PATH. This will
// restore cycles. The object will be mutated.

// The eval function is used to locate the values described by a PATH. The
// root object is kept in a $ variable. A regular expression is used to
// assure that the PATH is extremely well formed. The regexp contains nested
// * quantifiers. That has been known to have extremely bad performance
// problems on some browsers for very long strings. A PATH is expected to be
// reasonably short. A PATH is allowed to belong to a very restricted subset of
// Goessner's JSONPath.

// So,
//      var s = '[{"$ref":"$"}]';
//      return JSON.retrocycle(JSON.parse(s));
// produces an array containing a single element which is the array itself.

    var px = /^\$(?:\[(?:\d+|"(?:[^\\"\u0000-\u001f]|\\(?:[\\"\/bfnrt]|u[0-9a-zA-Z]{4}))*")\])*$/;

    (function rez(value) {

// The rez function walks recursively through the object looking for $ref
// properties. When it finds one that has a value that is a path, then it
// replaces the $ref object with a reference to the value that is found by
// the path.

      if (value && typeof value === 'object') {
        if (Array.isArray(value)) {
          value.forEach(function (element, i) {
            if (typeof element === 'object' && element !== null) {
              var path = element.$ref;
              if (typeof path === 'string' && px.test(path)) {
                value[i] = eval(path);
              } else {
                rez(element);
              }
            }
          });
        } else {
          Object.keys(value).forEach(function (name) {
            var item = value[name];
            if (typeof item === 'object' && item !== null) {
              var path = item.$ref;
              if (typeof path === 'string' && px.test(path)) {
                value[name] = eval(path);
              } else {
                rez(item);
              }
            }
          });
        }
      }
    }($));
    return $;
  };
}

// @ts-ignore
JSON.originalStringify = JSON.stringify;

// @ts-ignore
JSON.stringify = (value: any, replacer?: (this: any, key: string, value: any) => any, space?: string | number): string => {
  // @ts-ignore
  return JSON.originalStringify(JSON.decycle(value), replacer, space);
};

// @ts-ignore
JSON.originalParse = JSON.parse;

JSON.parse = (text: string, reviver?: (this: any, key: string, value: any) => any): any => {
  try {
    // @ts-ignore
    return JSON.originalParse(JSON.retrocycle(text), reviver);
  } catch (exception) {
    // TODO remove later!!!
    throw exception;
  }
};
