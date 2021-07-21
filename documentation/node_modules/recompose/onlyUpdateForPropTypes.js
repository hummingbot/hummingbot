"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = void 0;

var _onlyUpdateForKeys = _interopRequireDefault(require("./onlyUpdateForKeys"));

var _setDisplayName = _interopRequireDefault(require("./setDisplayName"));

var _wrapDisplayName = _interopRequireDefault(require("./wrapDisplayName"));

var _getDisplayName = _interopRequireDefault(require("./getDisplayName"));

var onlyUpdateForPropTypes = function onlyUpdateForPropTypes(BaseComponent) {
  var propTypes = BaseComponent.propTypes;

  if (process.env.NODE_ENV !== 'production') {
    if (!propTypes) {
      /* eslint-disable */
      console.error('A component without any `propTypes` was passed to ' + '`onlyUpdateForPropTypes()`. Check the implementation of the ' + ("component with display name \"" + (0, _getDisplayName.default)(BaseComponent) + "\"."));
      /* eslint-enable */
    }
  }

  var propKeys = Object.keys(propTypes || {});
  var OnlyUpdateForPropTypes = (0, _onlyUpdateForKeys.default)(propKeys)(BaseComponent);

  if (process.env.NODE_ENV !== 'production') {
    return (0, _setDisplayName.default)((0, _wrapDisplayName.default)(BaseComponent, 'onlyUpdateForPropTypes'))(OnlyUpdateForPropTypes);
  }

  return OnlyUpdateForPropTypes;
};

var _default = onlyUpdateForPropTypes;
exports.default = _default;