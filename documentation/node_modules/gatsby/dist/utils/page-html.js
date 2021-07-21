"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.remove = exports.getPageHtmlFilePath = void 0;

var _fsExtra = _interopRequireDefault(require("fs-extra"));

var _path = _interopRequireDefault(require("path"));

const checkForHtmlSuffix = pagePath => !/\.(html?)$/i.test(pagePath); // copied from https://github.com/markdalgleish/static-site-generator-webpack-plugin/blob/master/index.js#L161


const getPageHtmlFilePath = (dir, outputPath) => {
  let outputFileName = outputPath.replace(/^(\/|\\)/, ``); // Remove leading slashes for webpack-dev-server

  if (checkForHtmlSuffix(outputPath)) {
    outputFileName = _path.default.join(outputFileName, `index.html`);
  }

  return _path.default.join(dir, outputFileName);
};

exports.getPageHtmlFilePath = getPageHtmlFilePath;

const remove = async ({
  publicDir
}, pagePath) => {
  const filePath = getPageHtmlFilePath(publicDir, pagePath);

  if (_fsExtra.default.existsSync(filePath)) {
    return await _fsExtra.default.remove(filePath);
  }

  return Promise.resolve();
};

exports.remove = remove;
//# sourceMappingURL=page-html.js.map