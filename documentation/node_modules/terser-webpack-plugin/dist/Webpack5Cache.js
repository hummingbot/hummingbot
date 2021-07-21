"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;

var _getLazyHashedEtag = _interopRequireDefault(require("webpack/lib/cache/getLazyHashedEtag"));

var _serializeJavascript = _interopRequireDefault(require("serialize-javascript"));

var _webpack = require("webpack");

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

// eslint-disable-next-line import/extensions,import/no-unresolved
class Cache {
  constructor(compiler, compilation, options) {
    this.compiler = compiler;
    this.compilation = compilation;
    this.options = options;
  }

  isEnabled() {
    return !!this.compilation.cache;
  }

  createCacheIdent(task) {
    const {
      outputOptions: {
        hashSalt,
        hashDigest,
        hashDigestLength,
        hashFunction
      }
    } = this.compilation;

    const hash = _webpack.util.createHash(hashFunction);

    if (hashSalt) {
      hash.update(hashSalt);
    }

    hash.update((0, _serializeJavascript.default)(task.cacheKeys));
    const digest = hash.digest(hashDigest);
    const cacheKeys = digest.substr(0, hashDigestLength);
    return `${this.compilation.compilerPath}/TerserWebpackPlugin/${cacheKeys}/${task.file}`;
  }

  get(task) {
    // eslint-disable-next-line no-param-reassign
    task.cacheIdent = task.cacheIdent || this.createCacheIdent(task); // eslint-disable-next-line no-param-reassign

    task.cacheETag = task.cacheETag || (0, _getLazyHashedEtag.default)(task.asset);
    return new Promise((resolve, reject) => {
      this.compilation.cache.get(task.cacheIdent, task.cacheETag, (err, result) => {
        if (err) {
          reject(err);
        } else if (result) {
          resolve(result);
        } else {
          reject();
        }
      });
    });
  }

  store(task, data) {
    return new Promise((resolve, reject) => {
      this.compilation.cache.store(task.cacheIdent, task.cacheETag, data, err => {
        if (err) {
          reject(err);
        } else {
          resolve(data);
        }
      });
    });
  }

}

exports.default = Cache;