import * as React from 'react';
import { FormikContextType } from './types';
export declare const FormikContext: React.Context<FormikContextType<any>>;
export declare const FormikProvider: React.Provider<FormikContextType<any>>;
export declare const FormikConsumer: React.Consumer<FormikContextType<any>>;
export declare function useFormikContext<Values>(): FormikContextType<Values>;
