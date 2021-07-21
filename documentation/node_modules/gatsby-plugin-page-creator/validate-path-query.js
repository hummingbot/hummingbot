"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.validatePathQuery = validatePathQuery;

var _lodash = _interopRequireDefault(require("lodash"));

var _path = _interopRequireDefault(require("path"));

function validatePathQuery(filePath, extensions) {
  // Paths must start with /
  if (filePath.startsWith("/") !== true) {
    throw new Error("PageCreator: To query node \"gatsbyPath\" the \"filePath\" argument must be an absolute path, starting with a /\nPlease change this to: \"/" + filePath + "\"");
  } // Paths must not include file extension


  if (/\.[a-z]+$/i.test(filePath)) {
    throw new Error("PageCreator: To query node \"gatsbyPath\" the \"filePath\" argument must omit the file extension\nPlease change " + filePath + " to \"" + filePath.replace(/\.[a-z]+$/i, "") + "\"");
  } // Paths must not utilize src/pages


  if (filePath.includes("src/pages")) {
    throw new Error("PageCreator: To query node \"gatsbyPath\" the \"filePath\" argument must omit the src/pages prefix.\nPlease change this to: \"" + filePath.replace(/\/?src\/pages\//, "") + "\"");
  } // Paths must not include index


  if (/index$/.test(filePath)) {
    throw new Error("PageCreator: To query node \"gatsbyPath\" the \"filePath\" argument must omit index.\nPlease change this to: \"" + filePath.replace(/index$/, "") + "\"");
  }

  var absolutePath = _path.default.join(process.cwd(), "src/pages", filePath);

  var file = _lodash.default.flatten(extensions.map(function (ext) {
    return ["", _path.default.sep + "index"].map(function (index) {
      try {
        return require.resolve(absolutePath + index + ext);
      } catch (e) {
        return false;
      }
    });
  })).filter(Boolean);

  if (file.length === 0 || file[0].length === 0) {
    throw new Error("PageCreator: To query node \"gatsbyPath\" the \"filePath\" argument must represent a file that exists.\nUnable to find a file at: \"" + absolutePath + "\"");
  }
}