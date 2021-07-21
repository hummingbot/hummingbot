"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;

var _scms = _interopRequireDefault(require("./scms"));

var _processFiles = _interopRequireDefault(require("./processFiles"));

var _createIgnorer = _interopRequireDefault(require("./createIgnorer"));

var _createMatcher = _interopRequireDefault(require("./createMatcher"));

var _isSupportedExtension = _interopRequireDefault(require("./isSupportedExtension"));

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

var _default = (currentDirectory, {
  config,
  since,
  staged,
  pattern,
  restage = true,
  branch,
  bail,
  check,
  ignorePath,
  verbose,
  onFoundSinceRevision,
  onFoundChangedFiles,
  onPartiallyStagedFile,
  onExamineFile,
  onCheckFile,
  onWriteFile,
  resolveConfig = true
} = {}) => {
  const scm = (0, _scms.default)(currentDirectory);

  if (!scm) {
    throw new Error('Unable to detect a source control manager.');
  }

  const directory = scm.rootDirectory;
  const revision = since || scm.getSinceRevision(directory, {
    staged,
    branch
  });
  onFoundSinceRevision && onFoundSinceRevision(scm.name, revision);
  const rootIgnorer = (0, _createIgnorer.default)(directory, ignorePath);
  const cwdIgnorer = currentDirectory !== directory ? (0, _createIgnorer.default)(currentDirectory, ignorePath) : () => true;
  const changedFiles = scm.getChangedFiles(directory, revision, staged).filter((0, _isSupportedExtension.default)(resolveConfig)).filter((0, _createMatcher.default)(pattern)).filter(rootIgnorer).filter(cwdIgnorer);
  const unstagedFiles = staged ? scm.getUnstagedChangedFiles(directory, revision).filter(_isSupportedExtension.default).filter((0, _createMatcher.default)(pattern)).filter(rootIgnorer).filter(cwdIgnorer) : [];

  const wasFullyStaged = f => unstagedFiles.indexOf(f) < 0;

  onFoundChangedFiles && onFoundChangedFiles(changedFiles);
  const failReasons = new Set();
  (0, _processFiles.default)(directory, changedFiles, {
    check,
    config,
    onWriteFile: file => {
      onWriteFile && onWriteFile(file);

      if (bail) {
        failReasons.add('BAIL_ON_WRITE');
      }

      if (staged && restage) {
        if (wasFullyStaged(file)) {
          scm.stageFile(directory, file);
        } else {
          onPartiallyStagedFile && onPartiallyStagedFile(file);
          failReasons.add('PARTIALLY_STAGED_FILE');
        }
      }
    },
    onCheckFile: (file, isFormatted) => {
      onCheckFile && onCheckFile(file, isFormatted);

      if (!isFormatted) {
        failReasons.add('CHECK_FAILED');
      }
    },
    onExamineFile: verbose && onExamineFile
  });
  return {
    success: failReasons.size === 0,
    errors: Array.from(failReasons)
  };
};

exports.default = _default;