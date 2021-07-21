"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;

var _useSidecar = require("use-sidecar");

var _Trap = _interopRequireDefault(require("./Trap"));

var _medium = require("./medium");

var _default = (0, _useSidecar.exportSidecar)(_medium.mediumSidecar, _Trap["default"]);

exports["default"] = _default;