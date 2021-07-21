"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard");

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = void 0;

var _inheritsLoose2 = _interopRequireDefault(require("@babel/runtime/helpers/inheritsLoose"));

var _react = _interopRequireWildcard(require("react"));

var _getDisplayName = _interopRequireDefault(require("./getDisplayName"));

var _isClassComponent = _interopRequireDefault(require("./isClassComponent"));

var toClass = function toClass(baseComponent) {
  var _class, _temp;

  return (0, _isClassComponent.default)(baseComponent) ? baseComponent : (_temp = _class =
  /*#__PURE__*/
  function (_Component) {
    (0, _inheritsLoose2.default)(ToClass, _Component);

    function ToClass() {
      return _Component.apply(this, arguments) || this;
    }

    var _proto = ToClass.prototype;

    _proto.render = function render() {
      if (typeof baseComponent === 'string') {
        return _react.default.createElement(baseComponent, this.props);
      }

      return baseComponent(this.props, this.context);
    };

    return ToClass;
  }(_react.Component), _class.displayName = (0, _getDisplayName.default)(baseComponent), _class.propTypes = baseComponent.propTypes, _class.contextTypes = baseComponent.contextTypes, _class.defaultProps = baseComponent.defaultProps, _temp);
};

var _default = toClass;
exports.default = _default;