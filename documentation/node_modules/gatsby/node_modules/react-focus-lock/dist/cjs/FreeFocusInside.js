"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard");

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;

var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));

var React = _interopRequireWildcard(require("react"));

var _propTypes = _interopRequireDefault(require("prop-types"));

var constants = _interopRequireWildcard(require("focus-lock/constants"));

var _util = require("./util");

var FreeFocusInside = function FreeFocusInside(_ref) {
  var children = _ref.children,
      className = _ref.className;
  return /*#__PURE__*/React.createElement("div", (0, _extends2["default"])({}, (0, _util.inlineProp)(constants.FOCUS_ALLOW, true), {
    className: className
  }), children);
};

FreeFocusInside.propTypes = process.env.NODE_ENV !== "production" ? {
  children: _propTypes["default"].node.isRequired,
  className: _propTypes["default"].string
} : {};
FreeFocusInside.defaultProps = {
  className: undefined
};
var _default = FreeFocusInside;
exports["default"] = _default;