import * as React from 'react';
import { FormikContextType } from './types';
/**
 * Connect any component to Formik context, and inject as a prop called `formik`;
 * @param Comp React Component
 */
export declare function connect<OuterProps, Values = {}>(Comp: React.ComponentType<OuterProps & {
    formik: FormikContextType<Values>;
}>): React.ComponentType<OuterProps>;
