// @flow
/* eslint no-console:0 */
/**
 * This is a module for storing settings passed into KaTeX. It correctly handles
 * default settings.
 */

import utils from "./utils";
import ParseError from "./ParseError";
import {Token} from "./Token";

import type {AnyParseNode} from "./parseNode";
import type {MacroMap} from "./macros";

export type StrictFunction =
    (errorCode: string, errorMsg: string, token?: Token | AnyParseNode) =>
    ?(boolean | string);

export type TrustContextTypes = {
    "\\href": {|
        command: "\\href",
        url: string,
        protocol?: string,
    |},
    "\\includegraphics": {|
        command: "\\includegraphics",
        url: string,
        protocol?: string,
    |},
    "\\url": {|
        command: "\\url",
        url: string,
        protocol?: string,
    |},
    "\\htmlClass": {|
        command: "\\htmlClass",
        class: string,
    |},
    "\\htmlId": {|
        command: "\\htmlId",
        id: string,
    |},
    "\\htmlStyle": {|
        command: "\\htmlStyle",
        style: string,
    |},
    "\\htmlData": {|
        command: "\\htmlData",
        attributes: {[string]: string},
    |},
};
export type AnyTrustContext = $Values<TrustContextTypes>;
export type TrustFunction = (context: AnyTrustContext) => ?boolean;

export type SettingsOptions = {
    displayMode?: boolean;
    output?: "html" | "mathml" | "htmlAndMathml";
    leqno?: boolean;
    fleqn?: boolean;
    throwOnError?: boolean;
    errorColor?: string;
    macros?: MacroMap;
    minRuleThickness?: number;
    colorIsTextColor?: boolean;
    strict?: boolean | "ignore" | "warn" | "error" | StrictFunction;
    trust?: boolean | TrustFunction;
    maxSize?: number;
    maxExpand?: number;
    globalGroup?: boolean;
};

/**
 * The main Settings object
 *
 * The current options stored are:
 *  - displayMode: Whether the expression should be typeset as inline math
 *                 (false, the default), meaning that the math starts in
 *                 \textstyle and is placed in an inline-block); or as display
 *                 math (true), meaning that the math starts in \displaystyle
 *                 and is placed in a block with vertical margin.
 */
export default class Settings {
    displayMode: boolean;
    output: "html" | "mathml" | "htmlAndMathml";
    leqno: boolean;
    fleqn: boolean;
    throwOnError: boolean;
    errorColor: string;
    macros: MacroMap;
    minRuleThickness: number;
    colorIsTextColor: boolean;
    strict: boolean | "ignore" | "warn" | "error" | StrictFunction;
    trust: boolean | TrustFunction;
    maxSize: number;
    maxExpand: number;
    globalGroup: boolean;

    constructor(options: SettingsOptions) {
        // allow null options
        options = options || {};
        this.displayMode = utils.deflt(options.displayMode, false);
        this.output = utils.deflt(options.output, "htmlAndMathml");
        this.leqno = utils.deflt(options.leqno, false);
        this.fleqn = utils.deflt(options.fleqn, false);
        this.throwOnError = utils.deflt(options.throwOnError, true);
        this.errorColor = utils.deflt(options.errorColor, "#cc0000");
        this.macros = options.macros || {};
        this.minRuleThickness = Math.max(
            0,
            utils.deflt(options.minRuleThickness, 0)
        );
        this.colorIsTextColor = utils.deflt(options.colorIsTextColor, false);
        this.strict = utils.deflt(options.strict, "warn");
        this.trust = utils.deflt(options.trust, false);
        this.maxSize = Math.max(0, utils.deflt(options.maxSize, Infinity));
        this.maxExpand = Math.max(0, utils.deflt(options.maxExpand, 1000));
        this.globalGroup = utils.deflt(options.globalGroup, false);
    }

    /**
     * Report nonstrict (non-LaTeX-compatible) input.
     * Can safely not be called if `this.strict` is false in JavaScript.
     */
    reportNonstrict(errorCode: string, errorMsg: string,
                    token?: Token | AnyParseNode) {
        let strict = this.strict;
        if (typeof strict === "function") {
            // Allow return value of strict function to be boolean or string
            // (or null/undefined, meaning no further processing).
            strict = strict(errorCode, errorMsg, token);
        }
        if (!strict || strict === "ignore") {
            return;
        } else if (strict === true || strict === "error") {
            throw new ParseError(
                "LaTeX-incompatible input and strict mode is set to 'error': " +
                `${errorMsg} [${errorCode}]`, token);
        } else if (strict === "warn") {
            typeof console !== "undefined" && console.warn(
                "LaTeX-incompatible input and strict mode is set to 'warn': " +
                `${errorMsg} [${errorCode}]`);
        } else {  // won't happen in type-safe code
            typeof console !== "undefined" && console.warn(
                "LaTeX-incompatible input and strict mode is set to " +
                `unrecognized '${strict}': ${errorMsg} [${errorCode}]`);
        }
    }

    /**
     * Check whether to apply strict (LaTeX-adhering) behavior for unusual
     * input (like `\\`).  Unlike `nonstrict`, will not throw an error;
     * instead, "error" translates to a return value of `true`, while "ignore"
     * translates to a return value of `false`.  May still print a warning:
     * "warn" prints a warning and returns `false`.
     * This is for the second category of `errorCode`s listed in the README.
     */
    useStrictBehavior(errorCode: string, errorMsg: string,
                      token?: Token | AnyParseNode) {
        let strict = this.strict;
        if (typeof strict === "function") {
            // Allow return value of strict function to be boolean or string
            // (or null/undefined, meaning no further processing).
            // But catch any exceptions thrown by function, treating them
            // like "error".
            try {
                strict = strict(errorCode, errorMsg, token);
            } catch (error) {
                strict = "error";
            }
        }
        if (!strict || strict === "ignore") {
            return false;
        } else if (strict === true || strict === "error") {
            return true;
        } else if (strict === "warn") {
            typeof console !== "undefined" && console.warn(
                "LaTeX-incompatible input and strict mode is set to 'warn': " +
                `${errorMsg} [${errorCode}]`);
            return false;
        } else {  // won't happen in type-safe code
            typeof console !== "undefined" && console.warn(
                "LaTeX-incompatible input and strict mode is set to " +
                `unrecognized '${strict}': ${errorMsg} [${errorCode}]`);
            return false;
        }
    }

    /**
     * Check whether to test potentially dangerous input, and return
     * `true` (trusted) or `false` (untrusted).  The sole argument `context`
     * should be an object with `command` field specifying the relevant LaTeX
     * command (as a string starting with `\`), and any other arguments, etc.
     * If `context` has a `url` field, a `protocol` field will automatically
     * get added by this function (changing the specified object).
     */
    isTrusted(context: AnyTrustContext) {
        if (context.url && !context.protocol) {
            context.protocol = utils.protocolFromUrl(context.url);
        }
        const trust = typeof this.trust === "function"
            ? this.trust(context)
            : this.trust;
        return Boolean(trust);
    }
}
