"use strict";

exports.__esModule = true;
exports.default = void 0;

var isClassComponent = function isClassComponent(Component) {
  return Boolean(Component && Component.prototype && typeof Component.prototype.render === 'function');
};

var _default = isClassComponent;
exports.default = _default;