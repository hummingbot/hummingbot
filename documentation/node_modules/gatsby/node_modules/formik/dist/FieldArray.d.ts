import * as React from 'react';
import { SharedRenderProps, FormikProps } from './types';
export declare type FieldArrayRenderProps = ArrayHelpers & {
    form: FormikProps<any>;
    name: string;
};
export declare type FieldArrayConfig = {
    /** Really the path to the array field to be updated */
    name: string;
    /** Should field array validate the form AFTER array updates/changes? */
    validateOnChange?: boolean;
} & SharedRenderProps<FieldArrayRenderProps>;
export interface ArrayHelpers {
    /** Imperatively add a value to the end of an array */
    push: (obj: any) => void;
    /** Curried fn to add a value to the end of an array */
    handlePush: (obj: any) => () => void;
    /** Imperatively swap two values in an array */
    swap: (indexA: number, indexB: number) => void;
    /** Curried fn to swap two values in an array */
    handleSwap: (indexA: number, indexB: number) => () => void;
    /** Imperatively move an element in an array to another index */
    move: (from: number, to: number) => void;
    /** Imperatively move an element in an array to another index */
    handleMove: (from: number, to: number) => () => void;
    /** Imperatively insert an element at a given index into the array */
    insert: (index: number, value: any) => void;
    /** Curried fn to insert an element at a given index into the array */
    handleInsert: (index: number, value: any) => () => void;
    /** Imperatively replace a value at an index of an array  */
    replace: (index: number, value: any) => void;
    /** Curried fn to replace an element at a given index into the array */
    handleReplace: (index: number, value: any) => () => void;
    /** Imperatively add an element to the beginning of an array and return its length */
    unshift: (value: any) => number;
    /** Curried fn to add an element to the beginning of an array */
    handleUnshift: (value: any) => () => void;
    /** Curried fn to remove an element at an index of an array */
    handleRemove: (index: number) => () => void;
    /** Curried fn to remove a value from the end of the array */
    handlePop: () => () => void;
    /** Imperatively remove and element at an index of an array */
    remove<T>(index: number): T | undefined;
    /** Imperatively remove and return value from the end of the array */
    pop<T>(): T | undefined;
}
/**
 * Some array helpers!
 */
export declare const move: (array: any[], from: number, to: number) => unknown[];
export declare const swap: (arrayLike: ArrayLike<any>, indexA: number, indexB: number) => unknown[];
export declare const insert: (arrayLike: ArrayLike<any>, index: number, value: any) => unknown[];
export declare const replace: (arrayLike: ArrayLike<any>, index: number, value: any) => unknown[];
export declare const FieldArray: React.ComponentType<FieldArrayConfig>;
