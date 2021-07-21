"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.getConfigFile = getConfigFile;

var _fastestLevenshtein = require("fastest-levenshtein");

var _fsExtra = _interopRequireDefault(require("fs-extra"));

var _testRequireError = require("../utils/test-require-error");

var _reporter = _interopRequireDefault(require("gatsby-cli/lib/reporter"));

var _path = _interopRequireDefault(require("path"));

var _fsExistsCached = require("fs-exists-cached");

function isNearMatch(fileName, configName, distance) {
  if (!fileName) return false;
  return (0, _fastestLevenshtein.distance)(fileName, configName) <= distance;
}

async function getConfigFile(rootDir, configName, distance = 3) {
  const configPath = _path.default.join(rootDir, configName);

  let configFilePath = ``;
  let configModule;

  try {
    configFilePath = require.resolve(configPath);
    configModule = require(configFilePath);
  } catch (err) {
    const nearMatch = await _fsExtra.default.readdir(rootDir).then(files => files.find(file => {
      const fileName = file.split(rootDir).pop();
      return isNearMatch(fileName, configName, distance);
    }));

    if (!(0, _testRequireError.testRequireError)(configPath, err)) {
      _reporter.default.panic({
        id: `10123`,
        error: err,
        context: {
          configName,
          message: err.message
        }
      });
    } else if (nearMatch) {
      _reporter.default.panic({
        id: `10124`,
        error: err,
        context: {
          configName,
          nearMatch
        }
      });
    } else if ((0, _fsExistsCached.sync)(_path.default.join(rootDir, `src`, configName + `.js`))) {
      _reporter.default.panic({
        id: `10125`,
        context: {
          configName
        }
      });
    }
  }

  return {
    configModule,
    configFilePath
  };
}
//# sourceMappingURL=get-config-file.js.map