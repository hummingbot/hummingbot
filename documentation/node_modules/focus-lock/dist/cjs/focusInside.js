'use strict';

Object.defineProperty(exports, "__esModule", {
  value: true
});

var _allAffected = require('./utils/all-affected');

var _allAffected2 = _interopRequireDefault(_allAffected);

var _array = require('./utils/array');

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

var focusInFrame = function focusInFrame(frame) {
  return frame === document.activeElement;
};

var focusInsideIframe = function focusInsideIframe(topNode) {
  return !!(0, _array.arrayFind)((0, _array.toArray)(topNode.querySelectorAll('iframe')), focusInFrame);
};

var focusInside = function focusInside(topNode) {
  var activeElement = document && document.activeElement;

  if (!activeElement || activeElement.dataset && activeElement.dataset.focusGuard) {
    return false;
  }
  return (0, _allAffected2.default)(topNode).reduce(function (result, node) {
    return result || node.contains(activeElement) || focusInsideIframe(node);
  }, false);
};

exports.default = focusInside;