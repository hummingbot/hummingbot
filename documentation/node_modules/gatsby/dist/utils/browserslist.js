"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.getBrowsersList = void 0;

var _path = _interopRequireDefault(require("path"));

var _node = _interopRequireDefault(require("browserslist/node"));

const installedGatsbyVersion = directory => {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const {
      version
    } = require(_path.default.join(directory, `node_modules`, `gatsby`, `package.json`));

    return parseInt(version.split(`.`)[0], 10);
  } catch (e) {
    return undefined;
  }
};

const getBrowsersList = directory => {
  const fallback = installedGatsbyVersion(directory) === 1 ? [`>1%`, `last 2 versions`, `IE >= 9`] : [`>0.25%`, `not dead`];

  const config = _node.default.findConfig(directory);

  if (config && config.defaults) {
    return config.defaults;
  }

  return fallback;
};

exports.getBrowsersList = getBrowsersList;
//# sourceMappingURL=browserslist.js.map