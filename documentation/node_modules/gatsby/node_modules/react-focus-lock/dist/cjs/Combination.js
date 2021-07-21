"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard");

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;

var _objectWithoutProperties2 = _interopRequireDefault(require("@babel/runtime/helpers/objectWithoutProperties"));

var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));

var React = _interopRequireWildcard(require("react"));

var _Lock = _interopRequireDefault(require("./Lock"));

var _Trap = _interopRequireDefault(require("./Trap"));

/* that would be a BREAKING CHANGE!
// delaying sidecar execution till the first usage
const RequireSideCar = (props) => {
  // eslint-disable-next-line global-require
  const SideCar = require('./Trap').default;
  return <SideCar {...props} />;
};
*/
var FocusLockCombination = /*#__PURE__*/React.forwardRef(function (props, ref) {
  return /*#__PURE__*/React.createElement(_Lock["default"], (0, _extends2["default"])({
    sideCar: _Trap["default"],
    ref: ref
  }, props));
});

var _ref = _Lock["default"].propTypes || {},
    sideCar = _ref.sideCar,
    propTypes = (0, _objectWithoutProperties2["default"])(_ref, ["sideCar"]);

FocusLockCombination.propTypes = propTypes;
var _default = FocusLockCombination;
exports["default"] = _default;