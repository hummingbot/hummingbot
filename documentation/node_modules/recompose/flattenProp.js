"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = void 0;

var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));

var _react = require("react");

var _setDisplayName = _interopRequireDefault(require("./setDisplayName"));

var _wrapDisplayName = _interopRequireDefault(require("./wrapDisplayName"));

var flattenProp = function flattenProp(propName) {
  return function (BaseComponent) {
    var factory = (0, _react.createFactory)(BaseComponent);

    var FlattenProp = function FlattenProp(props) {
      return factory((0, _extends2.default)({}, props, props[propName]));
    };

    if (process.env.NODE_ENV !== 'production') {
      return (0, _setDisplayName.default)((0, _wrapDisplayName.default)(BaseComponent, 'flattenProp'))(FlattenProp);
    }

    return FlattenProp;
  };
};

var _default = flattenProp;
exports.default = _default;