//@flow
import defineFunction from "../defineFunction";
import ParseError from "../ParseError";
import {assertNodeType} from "../parseNode";

const globalMap = {
    "\\global": "\\global",
    "\\long": "\\\\globallong",
    "\\\\globallong": "\\\\globallong",
    "\\def": "\\gdef",
    "\\gdef": "\\gdef",
    "\\edef": "\\xdef",
    "\\xdef": "\\xdef",
    "\\let": "\\\\globallet",
    "\\futurelet": "\\\\globalfuture",
};

const checkControlSequence = (tok) => {
    const name = tok.text;
    if (/^(?:[\\{}$&#^_]|EOF)$/.test(name)) {
        throw new ParseError("Expected a control sequence", tok);
    }
    return name;
};

const getRHS = (parser) => {
    let tok = parser.gullet.popToken();
    if (tok.text === "=") { // consume optional equals
        tok = parser.gullet.popToken();
        if (tok.text === " ") { // consume one optional space
            tok = parser.gullet.popToken();
        }
    }
    return tok;
};

const letCommand = (parser, name, tok, global) => {
    let macro = parser.gullet.macros.get(tok.text);
    if (macro == null) {
        // don't expand it later even if a macro with the same name is defined
        // e.g., \let\foo=\frac \def\frac{\relax} \frac12
        tok.noexpand = true;
        macro = {
            tokens: [tok],
            numArgs: 0,
            // reproduce the same behavior in expansion
            unexpandable: !parser.gullet.isExpandable(tok.text),
        };
    }
    parser.gullet.macros.set(name, macro, global);
};

// <assignment> -> <non-macro assignment>|<macro assignment>
// <non-macro assignment> -> <simple assignment>|\global<non-macro assignment>
// <macro assignment> -> <definition>|<prefix><macro assignment>
// <prefix> -> \global|\long|\outer
defineFunction({
    type: "internal",
    names: [
        "\\global", "\\long",
        "\\\\globallong", // can’t be entered directly
    ],
    props: {
        numArgs: 0,
        allowedInText: true,
    },
    handler({parser, funcName}) {
        parser.consumeSpaces();
        const token = parser.fetch();
        if (globalMap[token.text]) {
            // KaTeX doesn't have \par, so ignore \long
            if (funcName === "\\global" || funcName === "\\\\globallong") {
                token.text = globalMap[token.text];
            }
            return assertNodeType(parser.parseFunction(), "internal");
        }
        throw new ParseError(`Invalid token after macro prefix`, token);
    },
});

// Basic support for macro definitions: \def, \gdef, \edef, \xdef
// <definition> -> <def><control sequence><definition text>
// <def> -> \def|\gdef|\edef|\xdef
// <definition text> -> <parameter text><left brace><balanced text><right brace>
defineFunction({
    type: "internal",
    names: ["\\def", "\\gdef", "\\edef", "\\xdef"],
    props: {
        numArgs: 0,
        allowedInText: true,
    },
    handler({parser, funcName}) {
        let arg = parser.gullet.consumeArgs(1)[0];
        if (arg.length !== 1) {
            throw new ParseError("\\gdef's first argument must be a macro name");
        }
        const name = arg[0].text;
        // Count argument specifiers, and check they are in the order #1 #2 ...
        let numArgs = 0;
        arg = parser.gullet.consumeArgs(1)[0];
        while (arg.length === 1 && arg[0].text === "#") {
            arg = parser.gullet.consumeArgs(1)[0];
            if (arg.length !== 1) {
                throw new ParseError(
                    `Invalid argument number length "${arg.length}"`);
            }
            if (!(/^[1-9]$/.test(arg[0].text))) {
                throw new ParseError(
                    `Invalid argument number "${arg[0].text}"`);
            }
            numArgs++;
            if (parseInt(arg[0].text) !== numArgs) {
                throw new ParseError(
                    `Argument number "${arg[0].text}" out of order`);
            }
            arg = parser.gullet.consumeArgs(1)[0];
        }
        if (funcName === "\\edef" || funcName === "\\xdef") {
            arg = parser.gullet.expandTokens(arg);
            arg.reverse(); // to fit in with stack order
        }
        // Final arg is the expansion of the macro
        parser.gullet.macros.set(name, {
            tokens: arg,
            numArgs,
        }, funcName === globalMap[funcName]);

        return {
            type: "internal",
            mode: parser.mode,
        };
    },
});

// <simple assignment> -> <let assignment>
// <let assignment> -> \futurelet<control sequence><token><token>
//     | \let<control sequence><equals><one optional space><token>
// <equals> -> <optional spaces>|<optional spaces>=
defineFunction({
    type: "internal",
    names: [
        "\\let",
        "\\\\globallet", // can’t be entered directly
    ],
    props: {
        numArgs: 0,
        allowedInText: true,
    },
    handler({parser, funcName}) {
        const name = checkControlSequence(parser.gullet.popToken());
        parser.gullet.consumeSpaces();
        const tok = getRHS(parser);
        letCommand(parser, name, tok, funcName === "\\\\globallet");
        return {
            type: "internal",
            mode: parser.mode,
        };
    },
});

// ref: https://www.tug.org/TUGboat/tb09-3/tb22bechtolsheim.pdf
defineFunction({
    type: "internal",
    names: [
        "\\futurelet",
        "\\\\globalfuture", // can’t be entered directly
    ],
    props: {
        numArgs: 0,
        allowedInText: true,
    },
    handler({parser, funcName}) {
        const name = checkControlSequence(parser.gullet.popToken());
        const middle = parser.gullet.popToken();
        const tok = parser.gullet.popToken();
        letCommand(parser, name, tok, funcName === "\\\\globalfuture");
        parser.gullet.pushToken(tok);
        parser.gullet.pushToken(middle);
        return {
            type: "internal",
            mode: parser.mode,
        };
    },
});
