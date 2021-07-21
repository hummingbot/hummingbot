import * as React from 'react';
import { FormikProps, GenericFieldHTMLAttributes, FieldMetaProps, FieldInputProps } from './types';
import { FieldConfig } from './Field';
export interface FastFieldProps<V = any> {
    field: FieldInputProps<V>;
    meta: FieldMetaProps<V>;
    form: FormikProps<V>;
}
export declare type FastFieldConfig<T> = FieldConfig & {
    /** Override FastField's default shouldComponentUpdate */
    shouldUpdate?: (nextProps: T & GenericFieldHTMLAttributes, props: {}) => boolean;
};
export declare type FastFieldAttributes<T> = GenericFieldHTMLAttributes & FastFieldConfig<T> & T;
export declare const FastField: React.ComponentType<any>;
