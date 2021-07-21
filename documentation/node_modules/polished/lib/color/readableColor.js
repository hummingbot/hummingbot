"use strict";

exports.__esModule = true;
exports.default = void 0;

var _getLuminance =
/*#__PURE__*/
_interopRequireDefault(
/*#__PURE__*/
require("./getLuminance"));

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

/**
 * Returns black or white for best contrast depending on the luminosity of the given color.
 * Follows W3C specs for readability at https://www.w3.org/TR/WCAG20-TECHS/G18.html
 *
 * @example
 * // Styles as object usage
 * const styles = {
 *   color: readableColor('#000'),
 *   color: readableColor('papayawhip'),
 *   color: readableColor('rgb(255,0,0)'),
 * }
 *
 * // styled-components usage
 * const div = styled.div`
 *   color: ${readableColor('#000')};
 *   color: ${readableColor('papayawhip')};
 *   color: ${readableColor('rgb(255,0,0)')};
 * `
 *
 * // CSS in JS Output
 *
 * element {
 *   color: "#fff";
 *   color: "#fff";
 *   color: "#000";
 * }
 */
function readableColor(color) {
  return (0, _getLuminance.default)(color) > 0.179 ? '#000' : '#fff';
}

var _default = readableColor;
exports.default = _default;
module.exports = exports.default;