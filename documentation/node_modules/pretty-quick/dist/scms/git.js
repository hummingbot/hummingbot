"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.stageFile = exports.getUnstagedChangedFiles = exports.getChangedFiles = exports.getSinceRevision = exports.detect = exports.name = void 0;

var _findUp = _interopRequireDefault(require("find-up"));

var _execa = _interopRequireDefault(require("execa"));

var _path = require("path");

var fs = _interopRequireWildcard(require("fs"));

function _getRequireWildcardCache() { if (typeof WeakMap !== "function") return null; var cache = new WeakMap(); _getRequireWildcardCache = function () { return cache; }; return cache; }

function _interopRequireWildcard(obj) { if (obj && obj.__esModule) { return obj; } if (obj === null || typeof obj !== "object" && typeof obj !== "function") { return { default: obj }; } var cache = _getRequireWildcardCache(); if (cache && cache.has(obj)) { return cache.get(obj); } var newObj = {}; var hasPropertyDescriptor = Object.defineProperty && Object.getOwnPropertyDescriptor; for (var key in obj) { if (Object.prototype.hasOwnProperty.call(obj, key)) { var desc = hasPropertyDescriptor ? Object.getOwnPropertyDescriptor(obj, key) : null; if (desc && (desc.get || desc.set)) { Object.defineProperty(newObj, key, desc); } else { newObj[key] = obj[key]; } } } newObj.default = obj; if (cache) { cache.set(obj, newObj); } return newObj; }

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

const name = 'git';
exports.name = name;

const detect = directory => {
  if (fs.existsSync((0, _path.join)(directory, '.git'))) {
    return directory;
  }

  const gitDirectory = _findUp.default.sync('.git', {
    cwd: directory,
    type: 'directory'
  });

  if (gitDirectory) {
    return (0, _path.dirname)(gitDirectory);
  }
};

exports.detect = detect;

const runGit = (directory, args) => _execa.default.sync('git', args, {
  cwd: directory
});

const getLines = execaResult => execaResult.stdout.split('\n');

const getSinceRevision = (directory, {
  staged,
  branch
}) => {
  try {
    const revision = staged ? 'HEAD' : runGit(directory, ['merge-base', 'HEAD', branch || 'master']).stdout.trim();
    return runGit(directory, ['rev-parse', '--short', revision]).stdout.trim();
  } catch (error) {
    if (/HEAD/.test(error.message) || staged && /Needed a single revision/.test(error.message)) {
      return null;
    }

    throw error;
  }
};

exports.getSinceRevision = getSinceRevision;

const getChangedFiles = (directory, revision, staged) => {
  return [...getLines(runGit(directory, ['diff', '--name-only', staged ? '--cached' : null, '--diff-filter=ACMRTUB', revision].filter(Boolean))), ...(staged ? [] : getLines(runGit(directory, ['ls-files', '--others', '--exclude-standard'])))].filter(Boolean);
};

exports.getChangedFiles = getChangedFiles;

const getUnstagedChangedFiles = directory => {
  return getChangedFiles(directory, null, false);
};

exports.getUnstagedChangedFiles = getUnstagedChangedFiles;

const stageFile = (directory, file) => {
  runGit(directory, ['add', file]);
};

exports.stageFile = stageFile;