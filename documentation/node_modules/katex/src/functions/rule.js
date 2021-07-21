// @flow
import buildCommon from "../buildCommon";
import defineFunction from "../defineFunction";
import mathMLTree from "../mathMLTree";
import {assertNodeType} from "../parseNode";
import {calculateSize} from "../units";

defineFunction({
    type: "rule",
    names: ["\\rule"],
    props: {
        numArgs: 2,
        numOptionalArgs: 1,
        argTypes: ["size", "size", "size"],
    },
    handler({parser}, args, optArgs) {
        const shift = optArgs[0];
        const width = assertNodeType(args[0], "size");
        const height = assertNodeType(args[1], "size");
        return {
            type: "rule",
            mode: parser.mode,
            shift: shift && assertNodeType(shift, "size").value,
            width: width.value,
            height: height.value,
        };
    },
    htmlBuilder(group, options) {
        // Make an empty span for the rule
        const rule = buildCommon.makeSpan(["mord", "rule"], [], options);

        // Calculate the shift, width, and height of the rule, and account for units
        const width = calculateSize(group.width, options);
        const height = calculateSize(group.height, options);
        const shift = (group.shift) ? calculateSize(group.shift, options) : 0;

        // Style the rule to the right size
        rule.style.borderRightWidth = width + "em";
        rule.style.borderTopWidth = height + "em";
        rule.style.bottom = shift + "em";

        // Record the height and width
        rule.width = width;
        rule.height = height + shift;
        rule.depth = -shift;
        // Font size is the number large enough that the browser will
        // reserve at least `absHeight` space above the baseline.
        // The 1.125 factor was empirically determined
        rule.maxFontSize = height * 1.125 * options.sizeMultiplier;

        return rule;
    },
    mathmlBuilder(group, options) {
        const width = calculateSize(group.width, options);
        const height = calculateSize(group.height, options);
        const shift = (group.shift) ? calculateSize(group.shift, options) : 0;
        const color = options.color && options.getColor() || "black";

        const rule = new mathMLTree.MathNode("mspace");
        rule.setAttribute("mathbackground", color);
        rule.setAttribute("width", width + "em");
        rule.setAttribute("height", height + "em");

        const wrapper = new mathMLTree.MathNode("mpadded", [rule]);
        if (shift >= 0) {
            wrapper.setAttribute("height", "+" + shift + "em");
        } else {
            wrapper.setAttribute("height", shift + "em");
            wrapper.setAttribute("depth", "+" + (-shift) + "em");
        }
        wrapper.setAttribute("voffset", shift + "em");

        return wrapper;
    },
});
