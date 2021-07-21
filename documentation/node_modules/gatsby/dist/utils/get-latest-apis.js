"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.getLatestAPIs = void 0;

var _path = _interopRequireDefault(require("path"));

var _fsExtra = _interopRequireDefault(require("fs-extra"));

var _axios = _interopRequireDefault(require("axios"));

const API_FILE = `https://unpkg.com/gatsby/apis.json`;

const ROOT = _path.default.join(__dirname, `..`, `..`);

const OUTPUT_FILE = _path.default.join(ROOT, `latest-apis.json`);

const getLatestAPIs = async () => {
  try {
    const {
      data
    } = await _axios.default.get(API_FILE, {
      timeout: 5000
    });
    await _fsExtra.default.writeFile(OUTPUT_FILE, JSON.stringify(data, null, 2), `utf8`);
    return data;
  } catch (e) {
    if (await _fsExtra.default.pathExists(OUTPUT_FILE)) {
      return _fsExtra.default.readJSON(OUTPUT_FILE);
    } // possible offline/network issue


    return _fsExtra.default.readJSON(_path.default.join(ROOT, `apis.json`)).catch(() => {
      return {
        browser: {},
        node: {},
        ssr: {}
      };
    });
  }
};

exports.getLatestAPIs = getLatestAPIs;
//# sourceMappingURL=get-latest-apis.js.map