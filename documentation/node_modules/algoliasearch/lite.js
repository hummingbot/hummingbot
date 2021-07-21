'use strict';

// For Node.js users, you will get the normal build (no lite)
// For browser users, this will be mapped to src/browser/builds/algoliasearchLite.js
// when used through browserify or webpack (see package.json browser field)
// This is done to ease universal applications (https://github.com/algolia/algoliasearch-client-js/issues/283)
module.exports = require('./index.js');
