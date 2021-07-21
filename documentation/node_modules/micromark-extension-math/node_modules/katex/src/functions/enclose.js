// @flow
import defineFunction from "../defineFunction";
import buildCommon from "../buildCommon";
import mathMLTree from "../mathMLTree";
import utils from "../utils";
import stretchy from "../stretchy";
import {assertNodeType} from "../parseNode";

import * as html from "../buildHTML";
import * as mml from "../buildMathML";


const htmlBuilder = (group, options) => {
    // \cancel, \bcancel, \xcancel, \sout, \fbox, \colorbox, \fcolorbox
    // Some groups can return document fragments.  Handle those by wrapping
    // them in a span.
    const inner = buildCommon.wrapFragment(
        html.buildGroup(group.body, options), options);

    const label = group.label.substr(1);
    const scale = options.sizeMultiplier;
    let img;
    let imgShift = 0;

    // In the LaTeX cancel package, line geometry is slightly different
    // depending on whether the subject is wider than it is tall, or vice versa.
    // We don't know the width of a group, so as a proxy, we test if
    // the subject is a single character. This captures most of the
    // subjects that should get the "tall" treatment.
    const isSingleChar = utils.isCharacterBox(group.body);

    if (label === "sout") {
        img = buildCommon.makeSpan(["stretchy", "sout"]);
        img.height = options.fontMetrics().defaultRuleThickness / scale;
        imgShift = -0.5 * options.fontMetrics().xHeight;

    } else {
        // Add horizontal padding
        if (/cancel/.test(label)) {
            if (!isSingleChar) {
                inner.classes.push("cancel-pad");
            }
        } else {
            inner.classes.push("boxpad");
        }

        // Add vertical padding
        let vertPad = 0;
        let ruleThickness = 0;
        // ref: cancel package: \advance\totalheight2\p@ % "+2"
        if (/box/.test(label)) {
            ruleThickness = Math.max(
                options.fontMetrics().fboxrule, // default
                options.minRuleThickness, // User override.
            );
            vertPad = options.fontMetrics().fboxsep +
                (label === "colorbox" ? 0 : ruleThickness);
        } else {
            vertPad = isSingleChar ? 0.2 : 0;
        }

        img = stretchy.encloseSpan(inner, label, vertPad, options);
        if (/fbox|boxed|fcolorbox/.test(label)) {
            img.style.borderStyle = "solid";
            img.style.borderWidth = `${ruleThickness}em`;
        }
        imgShift = inner.depth + vertPad;

        if (group.backgroundColor) {
            img.style.backgroundColor = group.backgroundColor;
            if (group.borderColor) {
                img.style.borderColor = group.borderColor;
            }
        }
    }

    let vlist;
    if (group.backgroundColor) {
        vlist = buildCommon.makeVList({
            positionType: "individualShift",
            children: [
                // Put the color background behind inner;
                {type: "elem", elem: img, shift: imgShift},
                {type: "elem", elem: inner, shift: 0},
            ],
        }, options);
    } else {
        vlist = buildCommon.makeVList({
            positionType: "individualShift",
            children: [
                // Write the \cancel stroke on top of inner.
                {
                    type: "elem",
                    elem: inner,
                    shift: 0,
                },
                {
                    type: "elem",
                    elem: img,
                    shift: imgShift,
                    wrapperClasses: /cancel/.test(label) ? ["svg-align"] : [],
                },
            ],
        }, options);
    }

    if (/cancel/.test(label)) {
        // The cancel package documentation says that cancel lines add their height
        // to the expression, but tests show that isn't how it actually works.
        vlist.height = inner.height;
        vlist.depth = inner.depth;
    }

    if (/cancel/.test(label) && !isSingleChar) {
        // cancel does not create horiz space for its line extension.
        return buildCommon.makeSpan(["mord", "cancel-lap"], [vlist], options);
    } else {
        return buildCommon.makeSpan(["mord"], [vlist], options);
    }
};

const mathmlBuilder = (group, options) => {
    let fboxsep = 0;
    const node = new mathMLTree.MathNode(
        (group.label.indexOf("colorbox") > -1) ? "mpadded" : "menclose",
        [mml.buildGroup(group.body, options)]
    );
    switch (group.label) {
        case "\\cancel":
            node.setAttribute("notation", "updiagonalstrike");
            break;
        case "\\bcancel":
            node.setAttribute("notation", "downdiagonalstrike");
            break;
        case "\\sout":
            node.setAttribute("notation", "horizontalstrike");
            break;
        case "\\fbox":
            node.setAttribute("notation", "box");
            break;
        case "\\fcolorbox":
        case "\\colorbox":
            // <menclose> doesn't have a good notation option. So use <mpadded>
            // instead. Set some attributes that come included with <menclose>.
            fboxsep = options.fontMetrics().fboxsep *
                options.fontMetrics().ptPerEm;
            node.setAttribute("width", `+${2 * fboxsep}pt`);
            node.setAttribute("height", `+${2 * fboxsep}pt`);
            node.setAttribute("lspace", `${fboxsep}pt`); //
            node.setAttribute("voffset", `${fboxsep}pt`);
            if (group.label === "\\fcolorbox") {
                const thk = Math.max(
                    options.fontMetrics().fboxrule, // default
                    options.minRuleThickness, // user override
                );
                node.setAttribute("style", "border: " + thk + "em solid " +
                    String(group.borderColor));
            }
            break;
        case "\\xcancel":
            node.setAttribute("notation", "updiagonalstrike downdiagonalstrike");
            break;
    }
    if (group.backgroundColor) {
        node.setAttribute("mathbackground", group.backgroundColor);
    }
    return node;
};

defineFunction({
    type: "enclose",
    names: ["\\colorbox"],
    props: {
        numArgs: 2,
        allowedInText: true,
        greediness: 3,
        argTypes: ["color", "text"],
    },
    handler({parser, funcName}, args, optArgs) {
        const color = assertNodeType(args[0], "color-token").color;
        const body = args[1];
        return {
            type: "enclose",
            mode: parser.mode,
            label: funcName,
            backgroundColor: color,
            body,
        };
    },
    htmlBuilder,
    mathmlBuilder,
});

defineFunction({
    type: "enclose",
    names: ["\\fcolorbox"],
    props: {
        numArgs: 3,
        allowedInText: true,
        greediness: 3,
        argTypes: ["color", "color", "text"],
    },
    handler({parser, funcName}, args, optArgs) {
        const borderColor = assertNodeType(args[0], "color-token").color;
        const backgroundColor = assertNodeType(args[1], "color-token").color;
        const body = args[2];
        return {
            type: "enclose",
            mode: parser.mode,
            label: funcName,
            backgroundColor,
            borderColor,
            body,
        };
    },
    htmlBuilder,
    mathmlBuilder,
});

defineFunction({
    type: "enclose",
    names: ["\\fbox"],
    props: {
        numArgs: 1,
        argTypes: ["hbox"],
        allowedInText: true,
    },
    handler({parser}, args) {
        return {
            type: "enclose",
            mode: parser.mode,
            label: "\\fbox",
            body: args[0],
        };
    },
});

defineFunction({
    type: "enclose",
    names: ["\\cancel", "\\bcancel", "\\xcancel", "\\sout"],
    props: {
        numArgs: 1,
    },
    handler({parser, funcName}, args, optArgs) {
        const body = args[0];
        return {
            type: "enclose",
            mode: parser.mode,
            label: funcName,
            body,
        };
    },
    htmlBuilder,
    mathmlBuilder,
});
