"use strict";

exports.__esModule = true;
exports.default = _default;

function _default(string, suffix) {
  return string.substr(-suffix.length) === suffix;
}

module.exports = exports.default;