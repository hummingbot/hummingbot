'use strict';

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.has2xxResponse = has2xxResponse;
exports.sortAlpha = sortAlpha;
exports.entries = entries;
exports.removePrefix = removePrefix;
exports.removeSuffix = removeSuffix;
exports.addSuffix = addSuffix;
exports.hyphenate = hyphenate;
exports.camelCase = camelCase;
exports.compareSortedArrays = compareSortedArrays;
const _camelCase = require('camelcase');

function has2xxResponse(res) {
  return res.responseCode >= 200 && res.responseCode < 300;
}

function sortAlpha(a, b) {
  // sort alphabetically in a deterministic way
  const shortLen = Math.min(a.length, b.length);
  for (let i = 0; i < shortLen; i++) {
    const aChar = a.charCodeAt(i);
    const bChar = b.charCodeAt(i);
    if (aChar !== bChar) {
      return aChar - bChar;
    }
  }
  return a.length - b.length;
}

function entries(obj) {
  const entries = [];
  if (obj) {
    for (const key in obj) {
      entries.push([key, obj[key]]);
    }
  }
  return entries;
}

function removePrefix(pattern, prefix) {
  if (pattern.startsWith(prefix)) {
    pattern = pattern.slice(prefix.length);
  }

  return pattern;
}

function removeSuffix(pattern, suffix) {
  if (pattern.endsWith(suffix)) {
    return pattern.slice(0, -suffix.length);
  }

  return pattern;
}

function addSuffix(pattern, suffix) {
  if (!pattern.endsWith(suffix)) {
    return pattern + suffix;
  }

  return pattern;
}

function hyphenate(str) {
  return str.replace(/[A-Z]/g, match => {
    return '-' + match.charAt(0).toLowerCase();
  });
}

function camelCase(str) {
  if (/[A-Z]/.test(str)) {
    return null;
  } else {
    return _camelCase(str);
  }
}

function compareSortedArrays(array1, array2) {
  if (array1.length !== array2.length) {
    return false;
  }
  for (let i = 0, len = array1.length; i < len; i++) {
    if (array1[i] !== array2[i]) {
      return false;
    }
  }
  return true;
}