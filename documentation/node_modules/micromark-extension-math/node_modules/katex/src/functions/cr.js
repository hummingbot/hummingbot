//@flow
// Row breaks within tabular environments, and line breaks at top level

import defineFunction from "../defineFunction";
import buildCommon from "../buildCommon";
import mathMLTree from "../mathMLTree";
import {calculateSize} from "../units";
import ParseError from "../ParseError";
import {assertNodeType} from "../parseNode";

// \\ is a macro mapping to either \cr or \newline.  Because they have the
// same signature, we implement them as one megafunction, with newRow
// indicating whether we're in the \cr case, and newLine indicating whether
// to break the line in the \newline case.

defineFunction({
    type: "cr",
    names: ["\\cr", "\\newline"],
    props: {
        numArgs: 0,
        numOptionalArgs: 1,
        argTypes: ["size"],
        allowedInText: true,
    },

    handler({parser, funcName}, args, optArgs) {
        const size = optArgs[0];
        const newRow = (funcName === "\\cr");
        let newLine = false;
        if (!newRow) {
            if (parser.settings.displayMode &&
                parser.settings.useStrictBehavior(
                    "newLineInDisplayMode", "In LaTeX, \\\\ or \\newline " +
                    "does nothing in display mode")) {
                newLine = false;
            } else {
                newLine = true;
            }
        }
        return {
            type: "cr",
            mode: parser.mode,
            newLine,
            newRow,
            size: size && assertNodeType(size, "size").value,
        };
    },

    // The following builders are called only at the top level,
    // not within tabular/array environments.

    htmlBuilder(group, options) {
        if (group.newRow) {
            throw new ParseError(
                "\\cr valid only within a tabular/array environment");
        }
        const span = buildCommon.makeSpan(["mspace"], [], options);
        if (group.newLine) {
            span.classes.push("newline");
            if (group.size) {
                span.style.marginTop =
                    calculateSize(group.size, options) + "em";
            }
        }
        return span;
    },

    mathmlBuilder(group, options) {
        const node = new mathMLTree.MathNode("mspace");
        if (group.newLine) {
            node.setAttribute("linebreak", "newline");
            if (group.size) {
                node.setAttribute("height",
                    calculateSize(group.size, options) + "em");
            }
        }
        return node;
    },
});
