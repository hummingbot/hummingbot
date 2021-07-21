"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.mediumSidecar = exports.mediumEffect = exports.mediumBlur = exports.mediumFocus = void 0;

var _useSidecar = require("use-sidecar");

var mediumFocus = (0, _useSidecar.createMedium)({}, function (_ref) {
  var target = _ref.target,
      currentTarget = _ref.currentTarget;
  return {
    target: target,
    currentTarget: currentTarget
  };
});
exports.mediumFocus = mediumFocus;
var mediumBlur = (0, _useSidecar.createMedium)();
exports.mediumBlur = mediumBlur;
var mediumEffect = (0, _useSidecar.createMedium)();
exports.mediumEffect = mediumEffect;
var mediumSidecar = (0, _useSidecar.createSidecarMedium)({
  async: true
});
exports.mediumSidecar = mediumSidecar;