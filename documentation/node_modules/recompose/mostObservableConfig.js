"use strict";

exports.__esModule = true;
exports.default = void 0;

var _most = require("most");

var config = {
  fromESObservable: _most.from || _most.Stream.from,
  toESObservable: function toESObservable(stream) {
    return stream;
  }
};
var _default = config;
exports.default = _default;