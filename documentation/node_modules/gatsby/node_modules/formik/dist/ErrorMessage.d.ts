import * as React from 'react';
export interface ErrorMessageProps {
    name: string;
    className?: string;
    component?: string | React.ComponentType;
    children?: (errorMessage: string) => React.ReactNode;
    render?: (errorMessage: string) => React.ReactNode;
}
export declare const ErrorMessage: React.ComponentType<ErrorMessageProps>;
