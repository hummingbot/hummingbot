"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = void 0;

var _react = require("react");

var _omit = _interopRequireDefault(require("./utils/omit"));

var componentFromProp = function componentFromProp(propName) {
  var Component = function Component(props) {
    return (0, _react.createElement)(props[propName], (0, _omit.default)(props, [propName]));
  };

  Component.displayName = "componentFromProp(" + propName + ")";
  return Component;
};

var _default = componentFromProp;
exports.default = _default;