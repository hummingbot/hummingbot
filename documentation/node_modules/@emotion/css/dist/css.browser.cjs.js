'use strict';

Object.defineProperty(exports, '__esModule', { value: true });

var serialize = require('@emotion/serialize');

function css() {
  for (var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++) {
    args[_key] = arguments[_key];
  }

  return serialize.serializeStyles(args);
}

exports.default = css;
