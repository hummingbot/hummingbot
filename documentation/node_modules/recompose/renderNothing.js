"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = void 0;

var _inheritsLoose2 = _interopRequireDefault(require("@babel/runtime/helpers/inheritsLoose"));

var _react = require("react");

var Nothing =
/*#__PURE__*/
function (_Component) {
  (0, _inheritsLoose2.default)(Nothing, _Component);

  function Nothing() {
    return _Component.apply(this, arguments) || this;
  }

  var _proto = Nothing.prototype;

  _proto.render = function render() {
    return null;
  };

  return Nothing;
}(_react.Component);

var renderNothing = function renderNothing(_) {
  return Nothing;
};

var _default = renderNothing;
exports.default = _default;