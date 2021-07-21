import * as React from 'react';
import { FormikHelpers, FormikProps, FormikSharedConfig, FormikValues, FormikTouched, FormikErrors } from './types';
/**
 * State, handlers, and helpers injected as props into the wrapped form component.
 * Used with withFormik()
 *
 * @deprecated  Use `OuterProps & FormikProps<Values>` instead.
 */
export declare type InjectedFormikProps<Props, Values> = Props & FormikProps<Values>;
/**
 * Formik helpers + { props }
 */
export declare type FormikBag<P, V> = {
    props: P;
} & FormikHelpers<V>;
/**
 * withFormik() configuration options. Backwards compatible.
 */
export interface WithFormikConfig<Props, Values extends FormikValues = FormikValues, DeprecatedPayload = Values> extends FormikSharedConfig<Props> {
    /**
     * Set the display name of the component. Useful for React DevTools.
     */
    displayName?: string;
    /**
     * Submission handler
     */
    handleSubmit: (values: Values, formikBag: FormikBag<Props, Values>) => void;
    /**
     * Map props to the form values
     */
    mapPropsToValues?: (props: Props) => Values;
    /**
     * Map props to the form status
     */
    mapPropsToStatus?: (props: Props) => any;
    /**
     * Map props to the form touched state
     */
    mapPropsToTouched?: (props: Props) => FormikTouched<Values>;
    /**
     * Map props to the form errors state
     */
    mapPropsToErrors?: (props: Props) => FormikErrors<Values>;
    /**
     * @deprecated in 0.9.0 (but needed to break TS types)
     */
    mapValuesToPayload?: (values: Values) => DeprecatedPayload;
    /**
     * A Yup Schema or a function that returns a Yup schema
     */
    validationSchema?: any | ((props: Props) => any);
    /**
     * Validation function. Must return an error object or promise that
     * throws an error object where that object keys map to corresponding value.
     */
    validate?: (values: Values, props: Props) => void | object | Promise<any>;
}
export declare type CompositeComponent<P> = React.ComponentClass<P> | React.StatelessComponent<P>;
export interface ComponentDecorator<TOwnProps, TMergedProps> {
    (component: CompositeComponent<TMergedProps>): React.ComponentType<TOwnProps>;
}
export interface InferableComponentDecorator<TOwnProps> {
    <T extends CompositeComponent<TOwnProps>>(component: T): T;
}
/**
 * A public higher-order component to access the imperative API
 */
export declare function withFormik<OuterProps extends object, Values extends FormikValues, Payload = Values>({ mapPropsToValues, ...config }: WithFormikConfig<OuterProps, Values, Payload>): ComponentDecorator<OuterProps, OuterProps & FormikProps<Values>>;
