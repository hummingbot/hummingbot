const { version } = require('webpack');

// Parse Webpack's major version: x.y.z => x
const webpackVersion = parseInt(version || '', 10);

let webpackGlobals = {};
if (webpackVersion === 5) {
  webpackGlobals = require('webpack/lib/RuntimeGlobals');
}

module.exports.refreshGlobal = `${webpackGlobals.require || '__webpack_require__'}.$Refresh$`;
module.exports.webpackVersion = webpackVersion;
