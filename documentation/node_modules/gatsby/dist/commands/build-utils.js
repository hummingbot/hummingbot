"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.removePageFiles = exports.collectRemovedPageData = exports.getChangedPageDataKeys = void 0;

var _fsExtra = _interopRequireDefault(require("fs-extra"));

var _path = _interopRequireDefault(require("path"));

var _pageHtml = require("../utils/page-html");

var _pageData = require("../utils/page-data");

const checkFolderIsEmpty = path => _fsExtra.default.existsSync(path) && !_fsExtra.default.readdirSync(path).length;

const getChangedPageDataKeys = (state, cachedPageData) => {
  if (cachedPageData && state.pageData) {
    const pageKeys = [];
    state.pageData.forEach((newPageDataHash, key) => {
      if (!cachedPageData.has(key)) {
        pageKeys.push(key);
      } else {
        const previousPageDataHash = cachedPageData.get(key);

        if (newPageDataHash !== previousPageDataHash) {
          pageKeys.push(key);
        }
      }
    });
    return pageKeys;
  }

  return [...state.pages.keys()];
};

exports.getChangedPageDataKeys = getChangedPageDataKeys;

const collectRemovedPageData = (state, cachedPageData) => {
  if (cachedPageData && state.pageData) {
    const deletedPageKeys = [];
    cachedPageData.forEach((_value, key) => {
      if (!state.pageData.has(key)) {
        deletedPageKeys.push(key);
      }
    });
    return deletedPageKeys;
  }

  return [];
};

exports.collectRemovedPageData = collectRemovedPageData;

const checkAndRemoveEmptyDir = (publicDir, pagePath) => {
  const pageHtmlDirectory = _path.default.dirname((0, _pageHtml.getPageHtmlFilePath)(publicDir, pagePath));

  const pageDataDirectory = _path.default.join(publicDir, `page-data`, (0, _pageData.fixedPagePath)(pagePath)); // if page's folder is empty also remove matching page-data folder


  if (checkFolderIsEmpty(pageHtmlDirectory)) {
    _fsExtra.default.removeSync(pageHtmlDirectory);
  }

  if (checkFolderIsEmpty(pageDataDirectory)) {
    _fsExtra.default.removeSync(pageDataDirectory);
  }
};

const sortedPageKeysByNestedLevel = pageKeys => pageKeys.sort((a, b) => {
  const currentPagePathValue = a.split(`/`).length;
  const previousPagePathValue = b.split(`/`).length;
  return previousPagePathValue - currentPagePathValue;
});

const removePageFiles = async (publicDir, pageKeys) => {
  const removePages = pageKeys.map(pagePath => (0, _pageHtml.remove)({
    publicDir
  }, pagePath));
  const removePageDataList = pageKeys.map(pagePath => (0, _pageData.removePageData)(publicDir, pagePath));
  return Promise.all([...removePages, ...removePageDataList]).then(() => {
    // Sort removed pageKeys by nested directories and remove if empty.
    sortedPageKeysByNestedLevel(pageKeys).forEach(pagePath => {
      checkAndRemoveEmptyDir(publicDir, pagePath);
    });
  });
};

exports.removePageFiles = removePageFiles;
//# sourceMappingURL=build-utils.js.map