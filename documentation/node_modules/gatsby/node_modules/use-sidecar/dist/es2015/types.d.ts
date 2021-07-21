import * as React from "react";
export declare type removeCb = () => void;
export declare type MediumCallback<T> = (data: T) => any;
export declare type MiddlewareCallback<T> = (data: T, assigned: boolean) => T;
export declare type SidePush<T> = {
    length?: number;
    push(data: T): void;
    filter(cb: (x: T) => boolean): SidePush<T>;
};
export interface SideMedium<T> {
    useMedium(effect: T): removeCb;
    assignMedium(handler: MediumCallback<T>): void;
    assignSyncMedium(handler: MediumCallback<T>): void;
    read(): T | undefined;
    options?: object;
}
export declare type DefaultOrNot<T> = {
    default: T;
} | T;
export declare type Importer<T> = () => Promise<DefaultOrNot<React.ComponentType<T>>>;
export declare type SideCarMedium = SideMedium<React.ComponentType>;
export declare type SideCarHOC = {
    sideCar: SideCarMedium;
};
export declare type SideCarComponent<T> = React.FunctionComponent<T & SideCarHOC>;
export declare type SideCarMediumOptions = {
    async?: boolean;
    ssr?: boolean;
};
