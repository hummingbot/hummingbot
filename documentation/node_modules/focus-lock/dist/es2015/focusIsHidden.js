import { toArray } from './utils/array';
import { FOCUS_ALLOW } from './constants';

var focusIsHidden = function focusIsHidden() {
  return document && toArray(document.querySelectorAll('[' + FOCUS_ALLOW + ']')).some(function (node) {
    return node.contains(document.activeElement);
  });
};

export default focusIsHidden;