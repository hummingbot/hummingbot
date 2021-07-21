"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = void 0;

var _react = require("react");

var _setDisplayName = _interopRequireDefault(require("./setDisplayName"));

var _wrapDisplayName = _interopRequireDefault(require("./wrapDisplayName"));

var identity = function identity(Component) {
  return Component;
};

var branch = function branch(test, left, right) {
  if (right === void 0) {
    right = identity;
  }

  return function (BaseComponent) {
    var leftFactory;
    var rightFactory;

    var Branch = function Branch(props) {
      if (test(props)) {
        leftFactory = leftFactory || (0, _react.createFactory)(left(BaseComponent));
        return leftFactory(props);
      }

      rightFactory = rightFactory || (0, _react.createFactory)(right(BaseComponent));
      return rightFactory(props);
    };

    if (process.env.NODE_ENV !== 'production') {
      return (0, _setDisplayName.default)((0, _wrapDisplayName.default)(BaseComponent, 'branch'))(Branch);
    }

    return Branch;
  };
};

var _default = branch;
exports.default = _default;