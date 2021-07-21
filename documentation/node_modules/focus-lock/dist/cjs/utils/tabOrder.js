'use strict';

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.orderByTabIndex = exports.tabSort = undefined;

var _array = require('./array');

var tabSort = exports.tabSort = function tabSort(a, b) {
  var tabDiff = a.tabIndex - b.tabIndex;
  var indexDiff = a.index - b.index;

  if (tabDiff) {
    if (!a.tabIndex) return 1;
    if (!b.tabIndex) return -1;
  }

  return tabDiff || indexDiff;
};

var orderByTabIndex = exports.orderByTabIndex = function orderByTabIndex(nodes, filterNegative, keepGuards) {
  return (0, _array.toArray)(nodes).map(function (node, index) {
    return {
      node: node,
      index: index,
      tabIndex: keepGuards && node.tabIndex === -1 ? (node.dataset || {}).focusGuard ? 0 : -1 : node.tabIndex
    };
  }).filter(function (data) {
    return !filterNegative || data.tabIndex >= 0;
  }).sort(tabSort);
};