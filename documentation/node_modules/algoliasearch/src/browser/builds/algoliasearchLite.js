'use strict';

var AlgoliaSearchCore = require('../../AlgoliaSearchCore.js');
var createAlgoliasearch = require('../createAlgoliasearch.js');

module.exports = createAlgoliasearch(AlgoliaSearchCore, 'Browser (lite)');
