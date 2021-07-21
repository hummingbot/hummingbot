"use strict";

exports.__esModule = true;
exports.default = void 0;

var _endsWith =
/*#__PURE__*/
_interopRequireDefault(
/*#__PURE__*/
require("./_endsWith"));

var _stripUnit =
/*#__PURE__*/
_interopRequireDefault(
/*#__PURE__*/
require("../helpers/stripUnit"));

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

/**
 * Factory function that creates pixel-to-x converters
 * @private
 */
var pxtoFactory = function pxtoFactory(to) {
  return function (pxval, base) {
    if (base === void 0) {
      base = '16px';
    }

    var newPxval = pxval;
    var newBase = base;

    if (typeof pxval === 'string') {
      if (!(0, _endsWith.default)(pxval, 'px')) {
        throw new Error("Expected a string ending in \"px\" or a number passed as the first argument to " + to + "(), got \"" + pxval + "\" instead.");
      }

      newPxval = (0, _stripUnit.default)(pxval);
    }

    if (typeof base === 'string') {
      if (!(0, _endsWith.default)(base, 'px')) {
        throw new Error("Expected a string ending in \"px\" or a number passed as the second argument to " + to + "(), got \"" + base + "\" instead.");
      }

      newBase = (0, _stripUnit.default)(base);
    }

    if (typeof newPxval === 'string') {
      throw new Error("Passed invalid pixel value (\"" + pxval + "\") to " + to + "(), please pass a value like \"12px\" or 12.");
    }

    if (typeof newBase === 'string') {
      throw new Error("Passed invalid base value (\"" + base + "\") to " + to + "(), please pass a value like \"12px\" or 12.");
    }

    return "" + newPxval / newBase + to;
  };
};

var _default = pxtoFactory;
exports.default = _default;
module.exports = exports.default;