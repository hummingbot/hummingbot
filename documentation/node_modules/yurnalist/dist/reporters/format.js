'use strict';

Object.defineProperty(exports, "__esModule", {
  value: true
});
function formatFunction() {
  for (var _len = arguments.length, strs = Array(_len), _key = 0; _key < _len; _key++) {
    strs[_key] = arguments[_key];
  }

  return strs.join(' ');
}

const defaultFormatter = exports.defaultFormatter = {
  bold: formatFunction,
  dim: formatFunction,
  italic: formatFunction,
  underline: formatFunction,
  inverse: formatFunction,
  strikethrough: formatFunction,
  black: formatFunction,
  red: formatFunction,
  green: formatFunction,
  yellow: formatFunction,
  blue: formatFunction,
  magenta: formatFunction,
  cyan: formatFunction,
  white: formatFunction,
  gray: formatFunction,
  grey: formatFunction,
  stripColor: formatFunction
};