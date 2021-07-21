"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.GatsbyWebpackStatsExtractor = void 0;

var _fsExtra = _interopRequireDefault(require("fs-extra"));

var _path = _interopRequireDefault(require("path"));

class GatsbyWebpackStatsExtractor {
  constructor() {
    this.plugin = {
      name: `GatsbyWebpackStatsExtractor`
    };
  }

  apply(compiler) {
    compiler.hooks.done.tapAsync(this.plugin.name, (stats, done) => {
      const assets = {};
      const assetsMap = {};

      for (const chunkGroup of stats.compilation.chunkGroups) {
        if (chunkGroup.name) {
          const files = [];

          for (const chunk of chunkGroup.chunks) {
            files.push(...chunk.files);
          }

          assets[chunkGroup.name] = files.filter(f => f.slice(-4) !== `.map`);
          assetsMap[chunkGroup.name] = files.filter(f => f.slice(-4) !== `.map` && f.slice(0, chunkGroup.name.length) === chunkGroup.name).map(filename => `/${filename}`);
        }
      }

      const webpackStats = { ...stats.toJson({
          all: false,
          chunkGroups: true
        }),
        assetsByChunkName: assets
      };

      _fsExtra.default.writeFile(_path.default.join(`public`, `chunk-map.json`), JSON.stringify(assetsMap), () => {
        _fsExtra.default.writeFile(_path.default.join(`public`, `webpack.stats.json`), JSON.stringify(webpackStats), done);
      });
    });
  }

}

exports.GatsbyWebpackStatsExtractor = GatsbyWebpackStatsExtractor;
//# sourceMappingURL=gatsby-webpack-stats-extractor.js.map