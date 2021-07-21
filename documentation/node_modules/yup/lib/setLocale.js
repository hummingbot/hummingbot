"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = setLocale;

var _locale = _interopRequireDefault(require("./locale"));

function setLocale(custom) {
  Object.keys(custom).forEach(function (type) {
    Object.keys(custom[type]).forEach(function (method) {
      _locale.default[type][method] = custom[type][method];
    });
  });
}

module.exports = exports["default"];