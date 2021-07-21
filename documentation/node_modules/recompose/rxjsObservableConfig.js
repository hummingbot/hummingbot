"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = void 0;

var _rxjs = _interopRequireDefault(require("rxjs"));

var config = {
  fromESObservable: _rxjs.default.Observable.from,
  toESObservable: function toESObservable(stream) {
    return stream;
  }
};
var _default = config;
exports.default = _default;