'use strict';

if (process.env.NODE_ENV === 'production') {
  module.exports = require('./tabs.cjs.production.min.js');
} else {
  module.exports = require('./tabs.cjs.development.js');
}