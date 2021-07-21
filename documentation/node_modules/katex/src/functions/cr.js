//@flow
// Row breaks within tabular environments, and line breaks at top level

import defineFunction from "../defineFunction";
import buildCommon from "../buildCommon";
import mathMLTree from "../mathMLTree";
import {calculateSize} from "../units";
import {assertNodeType} from "../parseNode";

// \DeclareRobustCommand\\{...\@xnewline}
defineFunction({
    type: "cr",
    names: ["\\\\"],
    props: {
        numArgs: 0,
        numOptionalArgs: 1,
        argTypes: ["size"],
        allowedInText: true,
    },

    handler({parser}, args, optArgs) {
        const size = optArgs[0];
        const newLine = !parser.settings.displayMode ||
            !parser.settings.useStrictBehavior(
                "newLineInDisplayMode", "In LaTeX, \\\\ or \\newline " +
                "does nothing in display mode");
        return {
            type: "cr",
            mode: parser.mode,
            newLine,
            size: size && assertNodeType(size, "size").value,
        };
    },

    // The following builders are called only at the top level,
    // not within tabular/array environments.

    htmlBuilder(group, options) {
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
