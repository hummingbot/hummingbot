// @flow
/**
 * This file contains the “gullet” where macros are expanded
 * until only non-macro tokens remain.
 */

import functions from "./functions";
import symbols from "./symbols";
import Lexer from "./Lexer";
import {Token} from "./Token";
import type {Mode} from "./types";
import ParseError from "./ParseError";
import Namespace from "./Namespace";
import builtinMacros from "./macros";

import type {MacroContextInterface, MacroDefinition, MacroExpansion}
    from "./macros";
import type Settings from "./Settings";

// List of commands that act like macros but aren't defined as a macro,
// function, or symbol.  Used in `isDefined`.
export const implicitCommands = {
    "\\relax": true,     // MacroExpander.js
    "^": true,           // Parser.js
    "_": true,           // Parser.js
    "\\limits": true,    // Parser.js
    "\\nolimits": true,  // Parser.js
};

export default class MacroExpander implements MacroContextInterface {
    settings: Settings;
    expansionCount: number;
    lexer: Lexer;
    macros: Namespace<MacroDefinition>;
    stack: Token[];
    mode: Mode;

    constructor(input: string, settings: Settings, mode: Mode) {
        this.settings = settings;
        this.expansionCount = 0;
        this.feed(input);
        // Make new global namespace
        this.macros = new Namespace(builtinMacros, settings.macros);
        this.mode = mode;
        this.stack = []; // contains tokens in REVERSE order
    }

    /**
     * Feed a new input string to the same MacroExpander
     * (with existing macros etc.).
     */
    feed(input: string) {
        this.lexer = new Lexer(input, this.settings);
    }

    /**
     * Switches between "text" and "math" modes.
     */
    switchMode(newMode: Mode) {
        this.mode = newMode;
    }

    /**
     * Start a new group nesting within all namespaces.
     */
    beginGroup() {
        this.macros.beginGroup();
    }

    /**
     * End current group nesting within all namespaces.
     */
    endGroup() {
        this.macros.endGroup();
    }

    /**
     * Returns the topmost token on the stack, without expanding it.
     * Similar in behavior to TeX's `\futurelet`.
     */
    future(): Token {
        if (this.stack.length === 0) {
            this.pushToken(this.lexer.lex());
        }
        return this.stack[this.stack.length - 1];
    }

    /**
     * Remove and return the next unexpanded token.
     */
    popToken(): Token {
        this.future();  // ensure non-empty stack
        return this.stack.pop();
    }

    /**
     * Add a given token to the token stack.  In particular, this get be used
     * to put back a token returned from one of the other methods.
     */
    pushToken(token: Token) {
        this.stack.push(token);
    }

    /**
     * Append an array of tokens to the token stack.
     */
    pushTokens(tokens: Token[]) {
        this.stack.push(...tokens);
    }

    /**
     * Consume all following space tokens, without expansion.
     */
    consumeSpaces() {
        for (;;) {
            const token = this.future();
            if (token.text === " ") {
                this.stack.pop();
            } else {
                break;
            }
        }
    }

    /**
     * Consume the specified number of arguments from the token stream,
     * and return the resulting array of arguments.
     */
    consumeArgs(numArgs: number): Token[][] {
        const args: Token[][] = [];
        // obtain arguments, either single token or balanced {…} group
        for (let i = 0; i < numArgs; ++i) {
            this.consumeSpaces();  // ignore spaces before each argument
            const startOfArg = this.popToken();
            if (startOfArg.text === "{") {
                const arg: Token[] = [];
                let depth = 1;
                while (depth !== 0) {
                    const tok = this.popToken();
                    arg.push(tok);
                    if (tok.text === "{") {
                        ++depth;
                    } else if (tok.text === "}") {
                        --depth;
                    } else if (tok.text === "EOF") {
                        throw new ParseError(
                            "End of input in macro argument",
                            startOfArg);
                    }
                }
                arg.pop(); // remove last }
                arg.reverse(); // like above, to fit in with stack order
                args[i] = arg;
            } else if (startOfArg.text === "EOF") {
                throw new ParseError(
                    "End of input expecting macro argument");
            } else {
                args[i] = [startOfArg];
            }
        }
        return args;
    }

    /**
     * Expand the next token only once if possible.
     *
     * If the token is expanded, the resulting tokens will be pushed onto
     * the stack in reverse order and will be returned as an array,
     * also in reverse order.
     *
     * If not, the next token will be returned without removing it
     * from the stack.  This case can be detected by a `Token` return value
     * instead of an `Array` return value.
     *
     * In either case, the next token will be on the top of the stack,
     * or the stack will be empty.
     *
     * Used to implement `expandAfterFuture` and `expandNextToken`.
     *
     * At the moment, macro expansion doesn't handle delimited macros,
     * i.e. things like those defined by \def\foo#1\end{…}.
     * See the TeX book page 202ff. for details on how those should behave.
     *
     * If expandableOnly, only expandable tokens are expanded and
     * an undefined control sequence results in an error.
     */
    expandOnce(expandableOnly?: boolean): Token | Token[] {
        const topToken = this.popToken();
        const name = topToken.text;
        const expansion = !topToken.noexpand ? this._getExpansion(name) : null;
        if (expansion == null || (expandableOnly && expansion.unexpandable)) {
            if (expandableOnly && expansion == null &&
                    name[0] === "\\" && !this.isDefined(name)) {
                throw new ParseError("Undefined control sequence: " + name);
            }
            this.pushToken(topToken);
            return topToken;
        }
        this.expansionCount++;
        if (this.expansionCount > this.settings.maxExpand) {
            throw new ParseError("Too many expansions: infinite loop or " +
                "need to increase maxExpand setting");
        }
        let tokens = expansion.tokens;
        if (expansion.numArgs) {
            const args = this.consumeArgs(expansion.numArgs);
            // paste arguments in place of the placeholders
            tokens = tokens.slice(); // make a shallow copy
            for (let i = tokens.length - 1; i >= 0; --i) {
                let tok = tokens[i];
                if (tok.text === "#") {
                    if (i === 0) {
                        throw new ParseError(
                            "Incomplete placeholder at end of macro body",
                            tok);
                    }
                    tok = tokens[--i]; // next token on stack
                    if (tok.text === "#") { // ## → #
                        tokens.splice(i + 1, 1); // drop first #
                    } else if (/^[1-9]$/.test(tok.text)) {
                        // replace the placeholder with the indicated argument
                        tokens.splice(i, 2, ...args[+tok.text - 1]);
                    } else {
                        throw new ParseError(
                            "Not a valid argument number",
                            tok);
                    }
                }
            }
        }
        // Concatenate expansion onto top of stack.
        this.pushTokens(tokens);
        return tokens;
    }

    /**
     * Expand the next token only once (if possible), and return the resulting
     * top token on the stack (without removing anything from the stack).
     * Similar in behavior to TeX's `\expandafter\futurelet`.
     * Equivalent to expandOnce() followed by future().
     */
    expandAfterFuture(): Token {
        this.expandOnce();
        return this.future();
    }

    /**
     * Recursively expand first token, then return first non-expandable token.
     */
    expandNextToken(): Token {
        for (;;) {
            const expanded = this.expandOnce();
            // expandOnce returns Token if and only if it's fully expanded.
            if (expanded instanceof Token) {
                // \relax stops the expansion, but shouldn't get returned (a
                // null return value couldn't get implemented as a function).
                // the token after \noexpand is interpreted as if its meaning
                // were ‘\relax’
                if (expanded.text === "\\relax" || expanded.treatAsRelax) {
                    this.stack.pop();
                } else {
                    return this.stack.pop();  // === expanded
                }
            }
        }

        // Flow unable to figure out that this pathway is impossible.
        // https://github.com/facebook/flow/issues/4808
        throw new Error(); // eslint-disable-line no-unreachable
    }

    /**
     * Fully expand the given macro name and return the resulting list of
     * tokens, or return `undefined` if no such macro is defined.
     */
    expandMacro(name: string): Token[] | void {
        return this.macros.has(name)
            ? this.expandTokens([new Token(name)]) : undefined;
    }

    /**
     * Fully expand the given token stream and return the resulting list of tokens
     */
    expandTokens(tokens: Token[]): Token[] {
        const output = [];
        const oldStackLength = this.stack.length;
        this.pushTokens(tokens);
        while (this.stack.length > oldStackLength) {
            const expanded = this.expandOnce(true); // expand only expandable tokens
            // expandOnce returns Token if and only if it's fully expanded.
            if (expanded instanceof Token) {
                if (expanded.treatAsRelax) {
                    // the expansion of \noexpand is the token itself
                    expanded.noexpand = false;
                    expanded.treatAsRelax = false;
                }
                output.push(this.stack.pop());
            }
        }
        return output;
    }

    /**
     * Fully expand the given macro name and return the result as a string,
     * or return `undefined` if no such macro is defined.
     */
    expandMacroAsText(name: string): string | void {
        const tokens = this.expandMacro(name);
        if (tokens) {
            return tokens.map((token) => token.text).join("");
        } else {
            return tokens;
        }
    }

    /**
     * Returns the expanded macro as a reversed array of tokens and a macro
     * argument count.  Or returns `null` if no such macro.
     */
    _getExpansion(name: string): ?MacroExpansion {
        const definition = this.macros.get(name);
        if (definition == null) { // mainly checking for undefined here
            return definition;
        }
        const expansion =
            typeof definition === "function" ? definition(this) : definition;
        if (typeof expansion === "string") {
            let numArgs = 0;
            if (expansion.indexOf("#") !== -1) {
                const stripped = expansion.replace(/##/g, "");
                while (stripped.indexOf("#" + (numArgs + 1)) !== -1) {
                    ++numArgs;
                }
            }
            const bodyLexer = new Lexer(expansion, this.settings);
            const tokens = [];
            let tok = bodyLexer.lex();
            while (tok.text !== "EOF") {
                tokens.push(tok);
                tok = bodyLexer.lex();
            }
            tokens.reverse(); // to fit in with stack using push and pop
            const expanded = {tokens, numArgs};
            return expanded;
        }

        return expansion;
    }

    /**
     * Determine whether a command is currently "defined" (has some
     * functionality), meaning that it's a macro (in the current group),
     * a function, a symbol, or one of the special commands listed in
     * `implicitCommands`.
     */
    isDefined(name: string): boolean {
        return this.macros.has(name) ||
            functions.hasOwnProperty(name) ||
            symbols.math.hasOwnProperty(name) ||
            symbols.text.hasOwnProperty(name) ||
            implicitCommands.hasOwnProperty(name);
    }

    /**
     * Determine whether a command is expandable.
     */
    isExpandable(name: string): boolean {
        const macro = this.macros.get(name);
        return macro != null ? typeof macro === "string"
                || typeof macro === "function" || !macro.unexpandable
            // TODO(ylem): #2085
            : functions.hasOwnProperty(name)/* && !functions[name].primitive*/;
    }
}
