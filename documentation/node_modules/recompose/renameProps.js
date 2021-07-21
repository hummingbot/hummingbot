"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = void 0;

var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));

var _omit = _interopRequireDefault(require("./utils/omit"));

var _pick = _interopRequireDefault(require("./utils/pick"));

var _mapProps = _interopRequireDefault(require("./mapProps"));

var _setDisplayName = _interopRequireDefault(require("./setDisplayName"));

var _wrapDisplayName = _interopRequireDefault(require("./wrapDisplayName"));

var keys = Object.keys;

var mapKeys = function mapKeys(obj, func) {
  return keys(obj).reduce(function (result, key) {
    var val = obj[key];
    /* eslint-disable no-param-reassign */

    result[func(val, key)] = val;
    /* eslint-enable no-param-reassign */

    return result;
  }, {});
};

var renameProps = function renameProps(nameMap) {
  var hoc = (0, _mapProps.default)(function (props) {
    return (0, _extends2.default)({}, (0, _omit.default)(props, keys(nameMap)), mapKeys((0, _pick.default)(props, keys(nameMap)), function (_, oldName) {
      return nameMap[oldName];
    }));
  });

  if (process.env.NODE_ENV !== 'production') {
    return function (BaseComponent) {
      return (0, _setDisplayName.default)((0, _wrapDisplayName.default)(BaseComponent, 'renameProps'))(hoc(BaseComponent));
    };
  }

  return hoc;
};

var _default = renameProps;
exports.default = _default;