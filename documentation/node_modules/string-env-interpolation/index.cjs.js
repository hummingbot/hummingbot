'use strict';

Object.defineProperty(exports, '__esModule', { value: true });

const defaults = typeof process !== "undefined" ? process.env : {};
function env(content, variables = defaults) {
    // https://regex101.com/r/k9saS6/2
    // Yes:
    //  ${NAME:DEFAULT}
    //  ${NAME:"DEFAULT"}
    //  ${NAME}
    // Not:
    //  ${NAME:}
    const R = /\$\{([A-Z0-9_]+(\:[^\}]+)?)\}/gi;
    return content.replace(R, (_, result) => {
        let [name, value, ...rest] = result.split(":");
        if (value) {
            if (rest && rest.length) {
                value = [value, ...rest].join(":");
            }
            value = value.trim();
            if (value.startsWith(`"`)) {
                value = value.replace(/^\"([^\"]+)\"$/g, "$1");
            }
            else if (value.startsWith(`'`)) {
                value = value.replace(/^\'([^\']+)\'$/g, "$1");
            }
        }
        return variables[name] ? String(variables[name]) : value;
    });
}

exports.env = env;
//# sourceMappingURL=index.cjs.js.map
