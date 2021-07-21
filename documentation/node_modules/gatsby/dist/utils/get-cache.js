"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.getCache = void 0;

var _cache = _interopRequireDefault(require("./cache"));

const caches = new Map();

const getCache = name => {
  let cache = caches.get(name);

  if (!cache) {
    cache = new _cache.default({
      name
    }).init();
    caches.set(name, cache);
  }

  return cache;
};

exports.getCache = getCache;
//# sourceMappingURL=get-cache.js.map