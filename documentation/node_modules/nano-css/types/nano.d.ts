import {RuleAddon} from '../addon/rule';
import {VCSSOMAddon} from '../addon/vcssom';
import {CSSOMAddon} from '../addon/cssom';
import {CssLikeObject} from './common';
import {ComponentAddon} from '../addon/component';
import {DecoratorAddon} from '../addon/decorator';
import {EmmetAddon} from '../addon/emmet';
import {SheetAddon} from '../addon/sheet';
import {UnitsAddon} from '../addon/units';
import {KeyframesAddon} from '../addon/keyframes';
import {AmpAddon} from '../addon/amp';
import {ArrayAddon} from '../addon/array';
import {CacheAddon} from '../addon/cache';
import {DruleAddon} from '../addon/drule';
import {DsheetAddon} from '../addon/dsheet';
import {ExtractAddon} from '../addon/extract';
import {GlobalAddon} from '../addon/global';
import {GoogleFontAddon} from '../addon/googleFont';
import {HydrateAddon} from '../addon/hydrate';

export * from '../addon/rule';
export * from '../addon/vcssom';
export * from '../addon/cssom';
export * from './common';
export * from '../addon/component';
export * from '../addon/decorator';
export * from '../addon/emmet';
export * from '../addon/sheet';
export * from '../addon/units';
export * from '../addon/keyframes';
export * from '../addon/amp';
export * from '../addon/array';
export * from '../addon/cache';
export * from '../addon/drule';
export * from '../addon/dsheet';
export * from '../addon/extract';
export * from '../addon/global';
export * from '../addon/googleFont';
export * from '../addon/hydrate';

export type Addons = RuleAddon &
    SheetAddon &
    ComponentAddon &
    UnitsAddon &
    KeyframesAddon &
    DecoratorAddon &
    EmmetAddon &
    CSSOMAddon &
    VCSSOMAddon &
    ArrayAddon &
    CacheAddon &
    DruleAddon &
    DsheetAddon &
    ExtractAddon &
    GlobalAddon &
    GoogleFontAddon &
    HydrateAddon &
    AmpAddon;

/**
 * nano-css main object.
 */
export interface NanoRenderer extends Partial<Addons> {
    /**
     * Equals to `true` if in browser environment.
     */
    client: boolean;

    /**
     * Raw CSS string. Populated in non-browser environment. Can be used to
     * render CSS server side.
     */
    raw: string;

    /**
     * Prefix to add to all class names and keyframe names.
     */
    pfx: string;

    /**
     * Add raw CSS rule. Example:
     *
     * ```js
     * nano.putRaw(`
     * .foo {
     *   color: red;
     * }
     * `);
     * ```
     */
    putRaw: (rawCss: string) => void;

    /**
     * Inject CSS given a selector and a CSS-like object.
     *
     * ```js
     * nano.put('.foo', {
     *     color: 'red',
     * });
     * ```
     *
     * Supports basic nesting.
     *
     * ```js
     * nano.put('.bar', {
     *     color: 'red',
     *     ':hover': {
     *         color: 'blue',
     *     },
     * });
     * ```
     */
    put: (selector: string, css: CssLikeObject, atrule?: string) => void;
}

export interface NanoOptions {
    /**
     * Prefix added to all class names and animation names.
     */
    pfx?: string;

    /**
     * Hyperscript function of your virtual DOM library. Needed only if you use
     * addons (like `jsx`, `style`, `styled`, `component`) that create components.
     *
     * ```js
     * const nano = create({
     *     h: React.createElement,
     * });
     * ```
     */
    h?: (...args) => any;

    /**
     * Stylesheet `<sheet>` to be used to inject CSS. If not provided, one will
     * be automatically created. You can also provide an external stylesheet
     * `<link>`, but then you need to set proper attributes on it: `rel="stylesheet" type="text/css"`.
     *
     * ```js
     * const nano = create({
     *     sh: typeof window === 'object' ? document.getElementById('nano-css') : undefined,
     * });
     * ```
     */
    sh?: CSSStyleSheet;

    /**
     * Whether to be chatty in DEV mode.
     */
    verbose?: boolean;

    /**
     * Defaults to `Object.assign`.
     */
    assign?: (...objects: object[]) => object;

    /**
     * Defaults to `JSON.stringify`.
     */
    stringify?: (obj: object) => string;
}

export type CreateNano = (options?: NanoOptions) => NanoRenderer;
