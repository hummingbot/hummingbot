"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;

var _multimatch = _interopRequireDefault(require("multimatch"));

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

const path = require('path');

var _default = pattern => {
  // Match everything if no pattern was given
  if (typeof pattern !== 'string' && !Array.isArray(pattern)) {
    return () => true;
  }

  const patterns = Array.isArray(pattern) ? pattern : [pattern];
  return file => (0, _multimatch.default)(path.normalize(file), patterns, {
    dot: true
  }).length > 0;
};

exports.default = _default;