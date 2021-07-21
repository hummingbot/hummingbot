"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = void 0;

var _kefir = _interopRequireDefault(require("kefir"));

var config = {
  fromESObservable: _kefir.default.fromESObservable,
  toESObservable: function toESObservable(stream) {
    return stream.toESObservable();
  }
};
var _default = config;
exports.default = _default;