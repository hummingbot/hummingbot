import * as React from 'react';
export declare type CircularProgressbarStyles = {
    root?: React.CSSProperties;
    trail?: React.CSSProperties;
    path?: React.CSSProperties;
    text?: React.CSSProperties;
    background?: React.CSSProperties;
};
export declare type CircularProgressbarDefaultProps = {
    background: boolean;
    backgroundPadding: number;
    circleRatio: number;
    classes: {
        root: string;
        trail: string;
        path: string;
        text: string;
        background: string;
    };
    className: string;
    counterClockwise: boolean;
    maxValue: number;
    minValue: number;
    strokeWidth: number;
    styles: CircularProgressbarStyles;
    text: string;
};
export declare type CircularProgressbarWrapperProps = {
    background?: boolean;
    backgroundPadding?: number;
    circleRatio?: number;
    classes?: {
        root: string;
        trail: string;
        path: string;
        text: string;
        background: string;
    };
    className?: string;
    counterClockwise?: boolean;
    maxValue?: number;
    minValue?: number;
    strokeWidth?: number;
    styles?: CircularProgressbarStyles;
    text?: string;
    value: number;
};
export declare type CircularProgressbarProps = CircularProgressbarDefaultProps & {
    value: number;
};
