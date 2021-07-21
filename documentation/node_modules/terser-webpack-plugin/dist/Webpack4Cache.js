"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;

var _os = _interopRequireDefault(require("os"));

var _cacache = _interopRequireDefault(require("cacache"));

var _findCacheDir = _interopRequireDefault(require("find-cache-dir"));

var _serializeJavascript = _interopRequireDefault(require("serialize-javascript"));

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

class Webpack4Cache {
  constructor(compiler, compilation, options) {
    this.options = options;
    this.cacheDir = options.cache === true ? Webpack4Cache.getCacheDirectory() : options.cache;
  }

  static getCacheDirectory() {
    return (0, _findCacheDir.default)({
      name: 'terser-webpack-plugin'
    }) || _os.default.tmpdir();
  }

  isEnabled() {
    return !!this.cacheDir;
  }

  get(task) {
    // eslint-disable-next-line no-param-reassign
    task.cacheIdent = task.cacheIdent || (0, _serializeJavascript.default)(task.cacheKeys);
    return _cacache.default.get(this.cacheDir, task.cacheIdent).then(({
      data
    }) => JSON.parse(data));
  }

  store(task, data) {
    return _cacache.default.put(this.cacheDir, task.cacheIdent, JSON.stringify(data));
  }

}

exports.default = Webpack4Cache;