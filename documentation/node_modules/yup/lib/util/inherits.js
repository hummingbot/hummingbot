"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = inherits;

var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));

function inherits(ctor, superCtor, spec) {
  ctor.prototype = Object.create(superCtor.prototype, {
    constructor: {
      value: ctor,
      enumerable: false,
      writable: true,
      configurable: true
    }
  });
  (0, _extends2.default)(ctor.prototype, spec);
}

module.exports = exports["default"];