'use strict';

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.isFile = exports.getRules = undefined;

var _fs = require('fs');

var _fs2 = _interopRequireDefault(_fs);

var _path = require('path');

var _path2 = _interopRequireDefault(_path);

var _glob = require('glob');

var _glob2 = _interopRequireDefault(_glob);

var _lodash = require('lodash');

var _lodash2 = _interopRequireDefault(_lodash);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

// @flow

var getRules = exports.getRules = function getRules() {
  var rulesFiles = _glob2.default.sync(_path2.default.resolve(__dirname, '../rules/*.js'));

  var rulesNames = rulesFiles.map(function (file) {
    return _path2.default.basename(file, '.js');
  }).map(function (name) {
    return [name, _lodash2.default.kebabCase(name)];
  });

  return rulesNames;
};

var isFile = exports.isFile = function isFile(filepath) {
  try {
    return _fs2.default.statSync(filepath).isFile();
  } catch (error) {
    return false;
  }
};