#!/usr/bin/env node
'use strict';

var _path = require('path');

var _path2 = _interopRequireDefault(_path);

var _fs = require('fs');

var _fs2 = _interopRequireDefault(_fs);

var _glob = require('glob');

var _glob2 = _interopRequireDefault(_glob);

var _lodash = require('lodash');

var _lodash2 = _interopRequireDefault(_lodash);

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

/**
 * @file This script is used to inline assertions into the README.md documents.
 */

var formatCodeSnippet = function formatCodeSnippet(setup) {
  var paragraphs = [];

  if (setup.options) {
    paragraphs.push('// Options: ' + JSON.stringify(setup.options));
  }

  if (setup.settings) {
    paragraphs.push('// Settings: ' + JSON.stringify(setup.settings));
  }

  paragraphs.push(setup.code);

  if (setup.errors) {
    setup.errors.forEach(function (message) {
      paragraphs.push('// Message: ' + message.message);
    });
  }

  if (setup.rules) {
    paragraphs.push('// Additional rules: ' + JSON.stringify(setup.rules));
  }

  return paragraphs.join('\n');
};

var getAssertions = function getAssertions() {
  var assertionFiles = _glob2.default.sync(_path2.default.resolve(__dirname, '../../tests/rules/assertions/*.js'));

  var assertionNames = _lodash2.default.map(assertionFiles, function (filePath) {
    return _path2.default.basename(filePath, '.js');
  });

  var assertionCodes = _lodash2.default.map(assertionFiles, function (filePath) {
    // eslint-disable-next-line global-require, import/no-dynamic-require
    var codes = require(filePath);

    return {
      invalid: _lodash2.default.map(codes.invalid, formatCodeSnippet),
      valid: _lodash2.default.map(codes.valid, formatCodeSnippet)
    };
  });

  return _lodash2.default.zipObject(assertionNames, assertionCodes);
};

var updateDocuments = function updateDocuments(assertions) {
  var readmeDocumentPath = _path2.default.join(__dirname, '../../README.md');
  var documentBody = void 0;

  documentBody = _fs2.default.readFileSync(readmeDocumentPath, 'utf8');

  documentBody = documentBody.replace(/<!-- assertions ([a-z]+?) -->/ig, function (assertionsBlock) {
    var exampleBody = void 0;

    var ruleName = assertionsBlock.match(/assertions ([a-z]+)/i)[1];

    var ruleAssertions = assertions[ruleName];

    if (!ruleAssertions) {
      throw new Error('No assertions available for rule "' + ruleName + '".');
    }

    exampleBody = '';

    if (ruleAssertions.invalid.length) {
      exampleBody += 'The following patterns are considered problems:\n\n```js\n' + ruleAssertions.invalid.join('\n\n') + '\n```\n\n';
    }

    if (ruleAssertions.valid.length) {
      exampleBody += 'The following patterns are not considered problems:\n\n```js\n' + ruleAssertions.valid.join('\n\n') + '\n```\n\n';
    }

    return exampleBody;
  });

  _fs2.default.writeFileSync(readmeDocumentPath, documentBody);
};

updateDocuments(getAssertions());