'use strict';

Object.defineProperty(exports, "__esModule", {
  value: true
});

var _array = require('./utils/array');

var _constants = require('./constants');

var focusIsHidden = function focusIsHidden() {
  return document && (0, _array.toArray)(document.querySelectorAll('[' + _constants.FOCUS_ALLOW + ']')).some(function (node) {
    return node.contains(document.activeElement);
  });
};

exports.default = focusIsHidden;