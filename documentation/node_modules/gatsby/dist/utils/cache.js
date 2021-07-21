"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = void 0;

var _cacheManager = _interopRequireDefault(require("cache-manager"));

var _fsExtra = _interopRequireDefault(require("fs-extra"));

var _cacheManagerFsHash = _interopRequireDefault(require("cache-manager-fs-hash"));

var _path = _interopRequireDefault(require("path"));

const MAX_CACHE_SIZE = 250;
const TTL = Number.MAX_SAFE_INTEGER;

class Cache {
  constructor({
    name = `db`,
    store = _cacheManagerFsHash.default
  } = {}) {
    this.name = name;
    this.store = store;
  }

  get directory() {
    return _path.default.join(process.cwd(), `.cache/caches/${this.name}`);
  }

  init() {
    _fsExtra.default.ensureDirSync(this.directory);

    const configs = [{
      store: `memory`,
      max: MAX_CACHE_SIZE,
      ttl: TTL
    }, {
      store: this.store,
      ttl: TTL,
      options: {
        path: this.directory,
        ttl: TTL
      }
    }];
    const caches = configs.map(cache => _cacheManager.default.caching(cache));
    this.cache = _cacheManager.default.multiCaching(caches);
    return this;
  }

  get(key) {
    return new Promise(resolve => {
      if (!this.cache) {
        throw new Error(`Cache wasn't initialised yet, please run the init method first`);
      }

      this.cache.get(key, (err, res) => {
        resolve(err ? undefined : res);
      });
    });
  }

  set(key, value, args = {
    ttl: TTL
  }) {
    return new Promise(resolve => {
      if (!this.cache) {
        throw new Error(`Cache wasn't initialised yet, please run the init method first`);
      }

      this.cache.set(key, value, args, err => {
        resolve(err ? undefined : value);
      });
    });
  }

}

exports.default = Cache;
//# sourceMappingURL=cache.js.map