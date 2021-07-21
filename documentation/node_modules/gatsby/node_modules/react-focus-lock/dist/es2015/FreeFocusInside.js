import _extends from "@babel/runtime/helpers/esm/extends";
import * as React from 'react';
import PropTypes from 'prop-types';
import * as constants from 'focus-lock/constants';
import { inlineProp } from './util';

var FreeFocusInside = function FreeFocusInside(_ref) {
  var children = _ref.children,
      className = _ref.className;
  return /*#__PURE__*/React.createElement("div", _extends({}, inlineProp(constants.FOCUS_ALLOW, true), {
    className: className
  }), children);
};

FreeFocusInside.propTypes = process.env.NODE_ENV !== "production" ? {
  children: PropTypes.node.isRequired,
  className: PropTypes.string
} : {};
FreeFocusInside.defaultProps = {
  className: undefined
};
export default FreeFocusInside;