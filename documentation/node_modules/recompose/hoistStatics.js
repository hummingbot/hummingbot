"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = void 0;

var _hoistNonReactStatics = _interopRequireDefault(require("hoist-non-react-statics"));

var hoistStatics = function hoistStatics(higherOrderComponent, blacklist) {
  return function (BaseComponent) {
    var NewComponent = higherOrderComponent(BaseComponent);
    (0, _hoistNonReactStatics.default)(NewComponent, BaseComponent, blacklist);
    return NewComponent;
  };
};

var _default = hoistStatics;
exports.default = _default;