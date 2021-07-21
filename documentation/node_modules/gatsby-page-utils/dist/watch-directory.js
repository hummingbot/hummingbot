"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard");

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.watchDirectory = watchDirectory;

var _regenerator = _interopRequireDefault(require("@babel/runtime/regenerator"));

var _asyncToGenerator2 = _interopRequireDefault(require("@babel/runtime/helpers/asyncToGenerator"));

var chokidar = _interopRequireWildcard(require("chokidar"));

var Promise = require("bluebird");

var _require = require("gatsby-core-utils"),
    slash = _require.slash;

function watchDirectory(_x, _x2, _x3, _x4) {
  return _watchDirectory.apply(this, arguments);
}

function _watchDirectory() {
  _watchDirectory = (0, _asyncToGenerator2.default)( /*#__PURE__*/_regenerator.default.mark(function _callee(path, glob, onNewFile, onRemovedFile) {
    return _regenerator.default.wrap(function _callee$(_context) {
      while (1) {
        switch (_context.prev = _context.next) {
          case 0:
            return _context.abrupt("return", new Promise(function (resolve) {
              chokidar.watch(glob, {
                cwd: path
              }).on("add", function (path) {
                path = slash(path);
                onNewFile(path);
              }).on("unlink", function (path) {
                path = slash(path);
                onRemovedFile(path);
              }).on("ready", function () {
                return resolve();
              });
            }));

          case 1:
          case "end":
            return _context.stop();
        }
      }
    }, _callee);
  }));
  return _watchDirectory.apply(this, arguments);
}