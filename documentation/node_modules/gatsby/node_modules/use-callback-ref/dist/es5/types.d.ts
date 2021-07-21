import * as React from 'react';
export declare type RefCallback<T> = (newValue: T | null) => void;
export declare type RefObject<T> = React.MutableRefObject<T | null>;
export declare type ReactRef<T> = RefCallback<T> | RefObject<T> | null;
