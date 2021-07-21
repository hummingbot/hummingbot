'use strict';

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.getParentAutofocusables = exports.getFocusables = undefined;

var _tabbables = require('./tabbables');

var _tabbables2 = _interopRequireDefault(_tabbables);

var _array = require('./array');

var _constants = require('../constants');

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

var queryTabbables = _tabbables2.default.join(',');
var queryGuardTabbables = queryTabbables + ', [data-focus-guard]';

var getFocusables = exports.getFocusables = function getFocusables(parents, withGuards) {
  return parents.reduce(function (acc, parent) {
    return acc.concat(
    // add all tabbables inside
    (0, _array.toArray)(parent.querySelectorAll(withGuards ? queryGuardTabbables : queryTabbables)),
    // add if node is tabble itself
    parent.parentNode ? (0, _array.toArray)(parent.parentNode.querySelectorAll(_tabbables2.default.join(','))).filter(function (node) {
      return node === parent;
    }) : []);
  }, []);
};

var getParentAutofocusables = exports.getParentAutofocusables = function getParentAutofocusables(parent) {
  var parentFocus = parent.querySelectorAll('[' + _constants.FOCUS_AUTO + ']');
  return (0, _array.toArray)(parentFocus).map(function (node) {
    return getFocusables([node]);
  }).reduce(function (acc, nodes) {
    return acc.concat(nodes);
  }, []);
};