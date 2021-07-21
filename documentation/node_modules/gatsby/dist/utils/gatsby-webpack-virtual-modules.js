"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard");

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.getAbsolutePathForVirtualModule = getAbsolutePathForVirtualModule;
exports.writeModule = writeModule;
exports.GatsbyWebpackVirtualModules = exports.VIRTUAL_MODULES_BASE_PATH = void 0;

var _webpackVirtualModules = _interopRequireDefault(require("webpack-virtual-modules"));

var path = _interopRequireWildcard(require("path"));

const fileContentLookup = {};
const instances = [];
const VIRTUAL_MODULES_BASE_PATH = `.cache/_this_is_virtual_fs_path_`;
exports.VIRTUAL_MODULES_BASE_PATH = VIRTUAL_MODULES_BASE_PATH;

class GatsbyWebpackVirtualModules {
  apply(compiler) {
    const virtualModules = new _webpackVirtualModules.default(fileContentLookup);
    virtualModules.apply(compiler);
    instances.push({
      writeModule: virtualModules.writeModule.bind(virtualModules)
    });
  }

}

exports.GatsbyWebpackVirtualModules = GatsbyWebpackVirtualModules;

function getAbsolutePathForVirtualModule(filePath) {
  return path.join(process.cwd(), VIRTUAL_MODULES_BASE_PATH, filePath);
}

function writeModule(filePath, fileContents) {
  const adjustedFilePath = getAbsolutePathForVirtualModule(filePath);

  if (fileContentLookup[adjustedFilePath] === fileContents) {
    // we already have this, no need to cause invalidation
    return;
  }

  fileContentLookup[adjustedFilePath] = fileContents;
  instances.forEach(instance => {
    instance.writeModule(adjustedFilePath, fileContents);
  });
}
//# sourceMappingURL=gatsby-webpack-virtual-modules.js.map