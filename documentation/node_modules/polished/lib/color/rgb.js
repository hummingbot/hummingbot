"use strict";

exports.__esModule = true;
exports.default = void 0;

var _reduceHexValue =
/*#__PURE__*/
_interopRequireDefault(
/*#__PURE__*/
require("../internalHelpers/_reduceHexValue"));

var _numberToHex =
/*#__PURE__*/
_interopRequireDefault(
/*#__PURE__*/
require("../internalHelpers/_numberToHex"));

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

/**
 * Returns a string value for the color. The returned result is the smallest possible hex notation.
 *
 * @example
 * // Styles as object usage
 * const styles = {
 *   background: rgb(255, 205, 100),
 *   background: rgb({ red: 255, green: 205, blue: 100 }),
 * }
 *
 * // styled-components usage
 * const div = styled.div`
 *   background: ${rgb(255, 205, 100)};
 *   background: ${rgb({ red: 255, green: 205, blue: 100 })};
 * `
 *
 * // CSS in JS Output
 *
 * element {
 *   background: "#ffcd64";
 *   background: "#ffcd64";
 * }
 */
function rgb(value, green, blue) {
  if (typeof value === 'number' && typeof green === 'number' && typeof blue === 'number') {
    return (0, _reduceHexValue.default)("#" + (0, _numberToHex.default)(value) + (0, _numberToHex.default)(green) + (0, _numberToHex.default)(blue));
  } else if (typeof value === 'object' && green === undefined && blue === undefined) {
    return (0, _reduceHexValue.default)("#" + (0, _numberToHex.default)(value.red) + (0, _numberToHex.default)(value.green) + (0, _numberToHex.default)(value.blue));
  }

  throw new Error('Passed invalid arguments to rgb, please pass multiple numbers e.g. rgb(255, 205, 100) or an object e.g. rgb({ red: 255, green: 205, blue: 100 }).');
}

var _default = rgb;
exports.default = _default;
module.exports = exports.default;