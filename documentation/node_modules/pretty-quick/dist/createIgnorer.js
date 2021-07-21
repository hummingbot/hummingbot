"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;

var _fs = require("fs");

var _path = require("path");

var _ignore = _interopRequireDefault(require("ignore"));

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

var _default = (directory, filename = '.prettierignore') => {
  const file = (0, _path.join)(directory, filename);

  if ((0, _fs.existsSync)(file)) {
    const text = (0, _fs.readFileSync)(file, 'utf8');
    const filter = (0, _ignore.default)().add(text).createFilter();
    return path => filter((0, _path.join)(path));
  }

  return () => true;
};

exports.default = _default;