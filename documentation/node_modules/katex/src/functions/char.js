// @flow
import defineFunction from "../defineFunction";
import ParseError from "../ParseError";
import {assertNodeType} from "../parseNode";

// \@char is an internal function that takes a grouped decimal argument like
// {123} and converts into symbol with code 123.  It is used by the *macro*
// \char defined in macros.js.
defineFunction({
    type: "textord",
    names: ["\\@char"],
    props: {
        numArgs: 1,
        allowedInText: true,
    },
    handler({parser}, args) {
        const arg = assertNodeType(args[0], "ordgroup");
        const group = arg.body;
        let number = "";
        for (let i = 0; i < group.length; i++) {
            const node = assertNodeType(group[i], "textord");
            number += node.text;
        }
        const code = parseInt(number);
        if (isNaN(code)) {
            throw new ParseError(`\\@char has non-numeric argument ${number}`);
        }
        return {
            type: "textord",
            mode: parser.mode,
            text: String.fromCharCode(code),
        };
    },
});
