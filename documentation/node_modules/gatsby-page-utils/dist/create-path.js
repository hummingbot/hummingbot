"use strict";

exports.__esModule = true;
exports.createPath = createPath;

var _path = require("path");

function createPath(filePath) {
  var _parse = (0, _path.parse)(filePath),
      dir = _parse.dir,
      name = _parse.name;

  var parsedName = name === "index" ? "" : name;
  return _path.posix.join("/", dir, parsedName, "/");
}