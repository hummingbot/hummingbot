'use strict';

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.pickFocusable = undefined;

var _correctFocus = require('./correctFocus');

var pickFirstFocus = function pickFirstFocus(nodes) {
  if (nodes[0] && nodes.length > 1) {
    return (0, _correctFocus.correctNode)(nodes[0], nodes);
  }
  return nodes[0];
};

var pickFocusable = exports.pickFocusable = function pickFocusable(nodes, index) {
  if (nodes.length > 1) {
    return nodes.indexOf((0, _correctFocus.correctNode)(nodes[index], nodes));
  }
  return index;
};

exports.default = pickFirstFocus;