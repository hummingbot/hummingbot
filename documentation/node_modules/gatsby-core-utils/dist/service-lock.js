"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.getServices = exports.getService = exports.createServiceLock = void 0;

var _path = _interopRequireDefault(require("path"));

var _tmp = _interopRequireDefault(require("tmp"));

var _properLockfile = _interopRequireDefault(require("proper-lockfile"));

var _fsExtra = _interopRequireDefault(require("fs-extra"));

var _xdgBasedir = _interopRequireDefault(require("xdg-basedir"));

var _createContentDigest = require("./create-content-digest");

var _ci = require("./ci");

/*
 * Service lock: handles service discovery for Gatsby develop processes
 * The problem:  the develop process starts a proxy server, the actual develop process and a websocket server for communication. The two latter ones have random ports that need to be discovered. We also cannot run multiple of the same site at the same time.
 * The solution: lockfiles! We create a folder in `.config/gatsby/sites/${sitePathHash} and then for each service write a JSON file with its data (e.g. developstatusserver.json) and lock that file (with developstatusserver.json.lock) so nobody can start the same service again.
 *
 * NOTE(@mxstbr): This is NOT EXPORTED from the main index.ts due to this relying on Node.js-specific APIs but core-utils also being used in browser environments. See https://github.com/jprichardson/node-fs-extra/issues/743
 */
const globalConfigPath = _xdgBasedir.default.config || _tmp.default.fileSync().name;

const getSiteDir = programPath => {
  const hash = (0, _createContentDigest.createContentDigest)(programPath);
  return _path.default.join(globalConfigPath, `gatsby`, `sites`, hash);
};

const DATA_FILE_EXTENSION = `.json`;

const getDataFilePath = (siteDir, serviceName) => _path.default.join(siteDir, `${serviceName}${DATA_FILE_EXTENSION}`);

const lockfileOptions = {
  // Use the minimum stale duration
  stale: 5000
};
const memoryServices = {};

const createServiceLock = async (programPath, serviceName, content) => {
  // NOTE(@mxstbr): In CI, we cannot reliably access the global config dir and do not need cross-process coordination anyway
  // so we fall back to storing the services in memory instead!
  if ((0, _ci.isCI)()) {
    if (memoryServices[serviceName]) return null;
    memoryServices[serviceName] = content;
    return async () => {
      delete memoryServices[serviceName];
    };
  }

  const siteDir = getSiteDir(programPath);
  await _fsExtra.default.ensureDir(siteDir);
  const serviceDataFile = getDataFilePath(siteDir, serviceName);

  try {
    await _fsExtra.default.writeFile(serviceDataFile, JSON.stringify(content));
    const unlock = await _properLockfile.default.lock(serviceDataFile, lockfileOptions);
    return unlock;
  } catch (err) {
    return null;
  }
};

exports.createServiceLock = createServiceLock;

const getService = async (programPath, serviceName, ignoreLockfile = false) => {
  if ((0, _ci.isCI)()) return memoryServices[serviceName] || null;
  const siteDir = getSiteDir(programPath);
  const serviceDataFile = getDataFilePath(siteDir, serviceName);

  try {
    if (ignoreLockfile || (await _properLockfile.default.check(serviceDataFile, lockfileOptions))) {
      return JSON.parse(await _fsExtra.default.readFile(serviceDataFile, `utf8`).catch(() => `null`));
    }

    return null;
  } catch (err) {
    return null;
  }
};

exports.getService = getService;

const getServices = async programPath => {
  if ((0, _ci.isCI)()) return memoryServices;
  const siteDir = getSiteDir(programPath);
  const serviceNames = (await _fsExtra.default.readdir(siteDir)).filter(file => file.endsWith(DATA_FILE_EXTENSION)).map(file => file.replace(DATA_FILE_EXTENSION, ``));
  const services = {};
  await Promise.all(serviceNames.map(async service => {
    services[service] = await getService(programPath, service, true);
  }));
  return services;
};

exports.getServices = getServices;