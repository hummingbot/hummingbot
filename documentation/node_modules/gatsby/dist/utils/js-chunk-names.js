"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.generateComponentChunkName = generateComponentChunkName;

var _lodash = require("lodash");

var _path = _interopRequireDefault(require("path"));

var _redux = require("../redux");

// unified routes adds support for files with [] and {},
// the problem with our generateComponentChunkName is that when you
// call kebabCase, is strips off characters like that. This means
// that when you have a app with this sort of setup, the resolutions fail
//
// src/pages/products/{id}.js (collection route)
// src/pages/products/[...id].js (should render when a non-matched id is passed in)
//
// without this function, what happens is that all visits to /products/__ resolve to only one
// of these because the componentChunkName ends up being duplicate. This function ensures that
// the {} and [] are kept in the componentChunkName. Also there are tests for this.
function replaceUnifiedRoutesKeys(kebabedName, filePath) {
  let newString = kebabedName;
  filePath.split(_path.default.sep).forEach(part => {
    if (part[0] === `[` || part[0] === `{`) {
      const match = /(\[(.*)\]|\{(.*)\})/.exec(part);
      newString = newString.replace(`-${match[2] || match[3]}-`, `-${match[0]}-`);
    }
  });
  return newString;
}

function generateComponentChunkName(componentPath) {
  const {
    program
  } = _redux.store.getState();

  const directory = (program === null || program === void 0 ? void 0 : program.directory) || `/`;

  const name = _path.default.relative(directory, componentPath);

  return `component---${replaceUnifiedRoutesKeys((0, _lodash.kebabCase)(name), name)}`;
}
//# sourceMappingURL=js-chunk-names.js.map