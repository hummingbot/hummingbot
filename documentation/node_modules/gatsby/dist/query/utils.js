"use strict";

exports.__esModule = true;
exports.pathToArray = pathToArray;
exports.formatErrorDetails = exports.indentString = void 0;

const indentString = string => string.replace(/\n/g, `\n  `);

exports.indentString = indentString;

const formatErrorDetails = errorDetails => Array.from(errorDetails.entries()).map(([name, details]) => `${name}:
  ${indentString(details.toString())}`).join(`\n`);

exports.formatErrorDetails = formatErrorDetails;

function pathToArray(path) {
  const flattened = [];
  let curr = path;

  while (curr) {
    flattened.push(curr.key);
    curr = curr.prev;
  }

  return flattened.reverse();
}
//# sourceMappingURL=utils.js.map