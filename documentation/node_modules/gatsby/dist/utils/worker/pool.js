"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.create = void 0;

var _jestWorker = _interopRequireDefault(require("jest-worker"));

var _gatsbyCoreUtils = require("gatsby-core-utils");

const create = () => new _jestWorker.default(require.resolve(`./child`), {
  numWorkers: (0, _gatsbyCoreUtils.cpuCoreCount)(),
  forkOptions: {
    silent: false
  }
});

exports.create = create;
//# sourceMappingURL=pool.js.map