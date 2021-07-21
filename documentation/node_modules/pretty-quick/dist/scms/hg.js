"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.stageFile = exports.getUnstagedChangedFiles = exports.getChangedFiles = exports.getSinceRevision = exports.detect = exports.name = void 0;

var _findUp = _interopRequireDefault(require("find-up"));

var _execa = _interopRequireDefault(require("execa"));

var _path = require("path");

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

const name = 'hg';
exports.name = name;

const detect = directory => {
  const hgDirectory = _findUp.default.sync('.hg', {
    cwd: directory,
    type: 'directory'
  });

  if (hgDirectory) {
    return (0, _path.dirname)(hgDirectory);
  }
};

exports.detect = detect;

const runHg = (directory, args) => _execa.default.sync('hg', args, {
  cwd: directory
});

const getLines = execaResult => execaResult.stdout.split('\n');

const getSinceRevision = (directory, {
  branch
}) => {
  const revision = runHg(directory, ['debugancestor', 'tip', branch || 'default']).stdout.trim();
  return runHg(directory, ['id', '-i', '-r', revision]).stdout.trim();
};

exports.getSinceRevision = getSinceRevision;

const getChangedFiles = (directory, revision) => {
  return [...getLines(runHg(directory, ['status', '-n', '-a', '-m', '--rev', revision]))].filter(Boolean);
};

exports.getChangedFiles = getChangedFiles;

const getUnstagedChangedFiles = () => {
  return [];
};

exports.getUnstagedChangedFiles = getUnstagedChangedFiles;

const stageFile = (directory, file) => {
  runHg(directory, ['add', file]);
};

exports.stageFile = stageFile;