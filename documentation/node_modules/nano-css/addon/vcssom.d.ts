import {CSSOMAddon} from './cssom';
import {Css} from './vcssom/cssToTree';
import {NanoRenderer} from '../types/nano';
import {CSSOMRule} from './cssom';
import {CssProps} from '../types/common';

export interface VRule {
    /**
     * CSS declarations, like `{color: 'red'}`
     */
    decl: CssProps;
    rule: CSSOMRule;

    /**
     * Re-render css rule according to new CSS declarations.
     * @param decl CSS declarations, like `{color: 'red'}`
     */
    diff(decl: CssProps);

    /**
     * Removes this `VRule` from CSSOM. After calling this method, you
     * cannot call `diff` anymore as this rule will be removed from style sheet.
     */
    del();
}

export interface VSheet {
    /**
     * Re-renders style sheet according to specified CSS-like object. The `css`
     * object is a 3-level tree structure:
     *
     * ```
     * {
     *   media-query-prelude: {
     *     selector: {
     *       declarations
     *     }
     *   }
     * }
     * ```
     *
     * Example:
     *
     * ```js
     * sheet.diff({
     *   '': {
     *     '.my-class': {
     *       color: 'red',
     *     },
     *     '.my-class:hover': {
     *       color: 'blue',
     *     },
     *   },
     *   '@media only screen and (max-width: 600px)': {
     *     '.my-class': {
     *       color: 'green',
     *     },
     *   },
     * });
     * ```
     *
     * @param css CSS-like object with media queries as top level.
     */
    diff(css: Css);
}

export interface VCSSOMAddon {
    VRule: new (selector: string, mediaQuery?: string) => VRule;
    VSheet: new () => VSheet;
}

export function addon(nano: NanoRenderer);
