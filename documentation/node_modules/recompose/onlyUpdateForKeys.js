"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = void 0;

var _shouldUpdate = _interopRequireDefault(require("./shouldUpdate"));

var _shallowEqual = _interopRequireDefault(require("./shallowEqual"));

var _setDisplayName = _interopRequireDefault(require("./setDisplayName"));

var _wrapDisplayName = _interopRequireDefault(require("./wrapDisplayName"));

var _pick = _interopRequireDefault(require("./utils/pick"));

var onlyUpdateForKeys = function onlyUpdateForKeys(propKeys) {
  var hoc = (0, _shouldUpdate.default)(function (props, nextProps) {
    return !(0, _shallowEqual.default)((0, _pick.default)(nextProps, propKeys), (0, _pick.default)(props, propKeys));
  });

  if (process.env.NODE_ENV !== 'production') {
    return function (BaseComponent) {
      return (0, _setDisplayName.default)((0, _wrapDisplayName.default)(BaseComponent, 'onlyUpdateForKeys'))(hoc(BaseComponent));
    };
  }

  return hoc;
};

var _default = onlyUpdateForKeys;
exports.default = _default;