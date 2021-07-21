#!/usr/bin/env node
'use strict';

var _fs = require('fs');

var _fs2 = _interopRequireDefault(_fs);

var _path = require('path');

var _path2 = _interopRequireDefault(_path);

var _utilities = require('./utilities');

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

var windows = function windows(array, size) {
  var output = [];

  for (var ii = 0; ii < array.length - size + 1; ii++) {
    output.push(array.slice(ii, ii + size));
  }

  return output;
};

// @flow

var getDocIndexRules = function getDocIndexRules() {
  var content = _fs2.default.readFileSync(_path2.default.resolve(__dirname, '../../.README/README.md'), 'utf-8');

  var rules = content.split('\n').map(function (line) {
    var match = /^{"gitdown": "include", "file": "([^"]+)"}$/.exec(line);

    if (match === null) {
      return null;
    } else {
      return match[1].replace('./rules/', '').replace('.md', '');
    }
  }).filter(function (rule) {
    return rule !== null;
  });

  if (rules.length === 0) {
    throw new Error('Docs checker is broken - it could not extract rules from docs index file.');
  }

  return rules;
};

var hasCorrectAssertions = function hasCorrectAssertions(docPath, name) {
  var content = _fs2.default.readFileSync(docPath, 'utf-8');

  var match = /<!-- assertions ([a-zA-Z]+) -->/.exec(content);

  if (match === null) {
    return false;
  } else {
    return match[1] === name;
  }
};

/**
 * Performed checks:
 *  - file `/.README/rules/<rule>.md` exists
 *  - file `/.README/rules/<rule>.md` contains correct assertions placeholder (`<!-- assertions ... -->`)
 *  - rule is included in gitdown directive in `/.README/README.md`
 *  - rules in `/.README/README.md` are alphabetically sorted
 */
var checkDocs = function checkDocs(rulesNames) {
  var docIndexRules = getDocIndexRules();

  var sorted = windows(docIndexRules, 2).every(function (chunk) {
    return chunk[0] < chunk[1];
  });

  if (!sorted) {
    throw new Error('Rules are not alphabetically sorted in `.README/README.md` file.');
  }

  var invalid = rulesNames.filter(function (names) {
    var docPath = _path2.default.resolve(__dirname, '../../.README/rules', names[1] + '.md');
    var docExists = (0, _utilities.isFile)(docPath);
    var inIndex = docIndexRules.includes(names[1]);
    var hasAssertions = docExists ? hasCorrectAssertions(docPath, names[0]) : false;

    return !(docExists && inIndex && hasAssertions);
  });

  if (invalid.length > 0) {
    var invalidList = invalid.map(function (names) {
      return names[0];
    }).join(', ');

    throw new Error('Docs checker encountered an error in: ' + invalidList + '. ' + 'Make sure that for every rule you created documentation file with assertions placeholder in camelCase ' + 'and included the file path in `.README/README.md` file.');
  }
};

checkDocs((0, _utilities.getRules)());