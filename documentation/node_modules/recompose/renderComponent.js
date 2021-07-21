"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = void 0;

var _react = require("react");

var _wrapDisplayName = _interopRequireDefault(require("./wrapDisplayName"));

var renderComponent = function renderComponent(Component) {
  return function (_) {
    var factory = (0, _react.createFactory)(Component);

    var RenderComponent = function RenderComponent(props) {
      return factory(props);
    };

    if (process.env.NODE_ENV !== 'production') {
      RenderComponent.displayName = (0, _wrapDisplayName.default)(Component, 'renderComponent');
    }

    return RenderComponent;
  };
};

var _default = renderComponent;
exports.default = _default;