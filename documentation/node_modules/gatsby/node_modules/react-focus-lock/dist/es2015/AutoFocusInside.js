import _extends from "@babel/runtime/helpers/esm/extends";
import * as React from 'react';
import PropTypes from 'prop-types';
import * as constants from 'focus-lock/constants';
import { inlineProp } from './util';

var AutoFocusInside = function AutoFocusInside(_ref) {
  var disabled = _ref.disabled,
      children = _ref.children,
      className = _ref.className;
  return /*#__PURE__*/React.createElement("div", _extends({}, inlineProp(constants.FOCUS_AUTO, !disabled), {
    className: className
  }), children);
};

AutoFocusInside.propTypes = process.env.NODE_ENV !== "production" ? {
  children: PropTypes.node.isRequired,
  disabled: PropTypes.bool,
  className: PropTypes.string
} : {};
AutoFocusInside.defaultProps = {
  disabled: false,
  className: undefined
};
export default AutoFocusInside;