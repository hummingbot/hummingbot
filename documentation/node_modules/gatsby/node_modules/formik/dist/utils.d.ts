import * as React from 'react';
/** @private is the value an empty array? */
export declare const isEmptyArray: (value?: any) => boolean;
/** @private is the given object a Function? */
export declare const isFunction: (obj: any) => obj is Function;
/** @private is the given object an Object? */
export declare const isObject: (obj: any) => obj is Object;
/** @private is the given object an integer? */
export declare const isInteger: (obj: any) => boolean;
/** @private is the given object a string? */
export declare const isString: (obj: any) => obj is string;
/** @private is the given object a NaN? */
export declare const isNaN: (obj: any) => boolean;
/** @private Does a React component have exactly 0 children? */
export declare const isEmptyChildren: (children: any) => boolean;
/** @private is the given object/value a promise? */
export declare const isPromise: (value: any) => value is PromiseLike<any>;
/** @private is the given object/value a type of synthetic event? */
export declare const isInputEvent: (value: any) => value is React.SyntheticEvent<any, Event>;
/**
 * Same as document.activeElement but wraps in a try-catch block. In IE it is
 * not safe to call document.activeElement if there is nothing focused.
 *
 * The activeElement will be null only if the document or document body is not
 * yet defined.
 *
 * @param {?Document} doc Defaults to current document.
 * @return {Element | null}
 * @see https://github.com/facebook/fbjs/blob/master/packages/fbjs/src/core/dom/getActiveElement.js
 */
export declare function getActiveElement(doc?: Document): Element | null;
/**
 * Deeply get a value from an object via its path.
 */
export declare function getIn(obj: any, key: string | string[], def?: any, p?: number): any;
/**
 * Deeply set a value from in object via it's path. If the value at `path`
 * has changed, return a shallow copy of obj with `value` set at `path`.
 * If `value` has not changed, return the original `obj`.
 *
 * Existing objects / arrays along `path` are also shallow copied. Sibling
 * objects along path retain the same internal js reference. Since new
 * objects / arrays are only created along `path`, we can test if anything
 * changed in a nested structure by comparing the object's reference in
 * the old and new object, similar to how russian doll cache invalidation
 * works.
 *
 * In earlier versions of this function, which used cloneDeep, there were
 * issues whereby settings a nested value would mutate the parent
 * instead of creating a new object. `clone` avoids that bug making a
 * shallow copy of the objects along the update path
 * so no object is mutated in place.
 *
 * Before changing this function, please read through the following
 * discussions.
 *
 * @see https://github.com/developit/linkstate
 * @see https://github.com/jaredpalmer/formik/pull/123
 */
export declare function setIn(obj: any, path: string, value: any): any;
/**
 * Recursively a set the same value for all keys and arrays nested object, cloning
 * @param object
 * @param value
 * @param visited
 * @param response
 */
export declare function setNestedObjectValues<T>(object: any, value: any, visited?: any, response?: any): T;
