"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = dedent;

/**
 * An ES6 string tag that fixes indentation. Also removes leading newlines
 * and trailing spaces and tabs, but keeps trailing newlines.
 *
 * Example usage:
 * const str = dedent`
 *   {
 *     test
 *   }
 * `;
 * str === "{\n  test\n}\n";
 */
function dedent(strings) {
  var str = '';

  for (var i = 0; i < strings.length; ++i) {
    str += strings[i];

    if (i < (arguments.length <= 1 ? 0 : arguments.length - 1)) {
      str += i + 1 < 1 || arguments.length <= i + 1 ? undefined : arguments[i + 1]; // interpolation
    }
  }

  var trimmedStr = str.replace(/^\n*/m, '') //  remove leading newline
  .replace(/[ \t]*$/, ''); // remove trailing spaces and tabs
  // fixes indentation by removing leading spaces and tabs from each line

  var indent = '';

  for (var _i2 = 0; _i2 < trimmedStr.length; _i2++) {
    var char = trimmedStr[_i2];

    if (char !== ' ' && char !== '\t') {
      break;
    }

    indent += char;
  }

  return trimmedStr.replace(RegExp('^' + indent, 'mg'), ''); // remove indent
}
