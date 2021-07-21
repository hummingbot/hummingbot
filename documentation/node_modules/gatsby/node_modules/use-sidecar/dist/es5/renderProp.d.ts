import * as React from 'react';
declare type CombinedProps<T extends any[], K> = {
    children: (...prop: T) => any;
} & K;
declare type RenderPropComponent<T extends any[], K> = React.ComponentType<CombinedProps<T, K>>;
interface Options {
    pure?: boolean;
}
export declare function renderCar<T extends any[], K>(WrappedComponent: RenderPropComponent<T, K>, defaults: (props: K) => T, options?: Options): (props: CombinedProps<T, K>) => JSX.Element;
export {};
