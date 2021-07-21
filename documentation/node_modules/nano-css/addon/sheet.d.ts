import {CssLikeObject} from '../types/common';
import {NanoRenderer} from '../types/nano';

export interface SheetAddon {
    /**
     * Creates a collection of CSS rules.
     *
     * ```js
     * const classes = sheet({
     *     wrapper: {
     *         border: '1px solid red',
     *     },
     *     button: {
     *         color: 'red',
     *     },
     * });
     * ```
     */
    sheet: (cssMap: {[s: string]: CssLikeObject}, block?: string) => {[s: string]: string};
}

export function addon(nano: NanoRenderer);
