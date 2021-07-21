"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = void 0;

var _extends3 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));

var _omit = _interopRequireDefault(require("./utils/omit"));

var _mapProps = _interopRequireDefault(require("./mapProps"));

var _setDisplayName = _interopRequireDefault(require("./setDisplayName"));

var _wrapDisplayName = _interopRequireDefault(require("./wrapDisplayName"));

var renameProp = function renameProp(oldName, newName) {
  var hoc = (0, _mapProps.default)(function (props) {
    var _extends2;

    return (0, _extends3.default)({}, (0, _omit.default)(props, [oldName]), (_extends2 = {}, _extends2[newName] = props[oldName], _extends2));
  });

  if (process.env.NODE_ENV !== 'production') {
    return function (BaseComponent) {
      return (0, _setDisplayName.default)((0, _wrapDisplayName.default)(BaseComponent, 'renameProp'))(hoc(BaseComponent));
    };
  }

  return hoc;
};

var _default = renameProp;
exports.default = _default;