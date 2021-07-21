"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.prepareRegex = void 0;

var _lodash = _interopRequireDefault(require("lodash"));

const prepareRegex = str => {
  const exploded = str.split(`/`);
  const regex = new RegExp(exploded.slice(1, -1).join(`/`) // Double escaping is needed to get past the GraphQL parser,
  // but single escaping is needed for the RegExp constructor,
  // i.e. `"\\\\w+"` for `/\w+/`.
  .replace(/\\\\/, `\\`), _lodash.default.last(exploded));
  return regex;
};

exports.prepareRegex = prepareRegex;
//# sourceMappingURL=prepare-regex.js.map