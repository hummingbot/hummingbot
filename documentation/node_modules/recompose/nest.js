"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = void 0;

var _objectWithoutPropertiesLoose2 = _interopRequireDefault(require("@babel/runtime/helpers/objectWithoutPropertiesLoose"));

var _react = require("react");

var _getDisplayName = _interopRequireDefault(require("./getDisplayName"));

var nest = function nest() {
  for (var _len = arguments.length, Components = new Array(_len), _key = 0; _key < _len; _key++) {
    Components[_key] = arguments[_key];
  }

  var factories = Components.map(_react.createFactory);

  var Nest = function Nest(_ref) {
    var children = _ref.children,
        props = (0, _objectWithoutPropertiesLoose2.default)(_ref, ["children"]);
    return factories.reduceRight(function (child, factory) {
      return factory(props, child);
    }, children);
  };

  if (process.env.NODE_ENV !== 'production') {
    var displayNames = Components.map(_getDisplayName.default);
    Nest.displayName = "nest(" + displayNames.join(', ') + ")";
  }

  return Nest;
};

var _default = nest;
exports.default = _default;