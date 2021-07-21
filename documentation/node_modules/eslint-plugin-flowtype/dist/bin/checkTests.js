'use strict';

var _fs = require('fs');

var _fs2 = _interopRequireDefault(_fs);

var _path = require('path');

var _path2 = _interopRequireDefault(_path);

var _utilities = require('./utilities');

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

var getTestIndexRules = function getTestIndexRules() {
  var content = _fs2.default.readFileSync(_path2.default.resolve(__dirname, '../../tests/rules/index.js'), 'utf-8');

  var result = content.split('\n').reduce(function (acc, line) {
    if (acc.inRulesArray) {
      if (line === '];') {
        acc.inRulesArray = false;
      } else {
        acc.rules.push(line.replace(/^\s*'([^']+)',?$/, '$1'));
      }
    } else if (line === 'const reportingRules = [') {
      acc.inRulesArray = true;
    }

    return acc;
  }, {
    inRulesArray: false,
    rules: []
  });

  var rules = result.rules;

  if (rules.length === 0) {
    throw new Error('Tests checker is broken - it could not extract rules from test index file.');
  }

  return rules;
};

/**
 * Performed checks:
 *  - file `/tests/rules/assertions/<rule>.js` exists
 *  - rule is included in `reportingRules` variable in `/tests/rules/index.js`
 */
// @flow

var checkTests = function checkTests(rulesNames) {
  var testIndexRules = getTestIndexRules();

  var invalid = rulesNames.filter(function (names) {
    var testExists = (0, _utilities.isFile)(_path2.default.resolve(__dirname, '../../tests/rules/assertions', names[0] + '.js'));
    var inIndex = testIndexRules.includes(names[1]);

    return !(testExists && inIndex);
  });

  if (invalid.length > 0) {
    var invalidList = invalid.map(function (names) {
      return names[0];
    }).join(', ');

    throw new Error('Tests checker encountered an error in: ' + invalidList + '. ' + 'Make sure that for every rule you created test suite and included the rule name in `tests/rules/index.js` file.');
  }
};

checkTests((0, _utilities.getRules)());