/**
 * Copyright(c) node-modules and other contributors.
 * MIT Licensed
 *
 * Authors:
 *   fengmk2 <m@fengmk2.com> (http://fengmk2.com)
 */

'use strict';

/**
 * Module dependencies.
 */

var util = require('util');
var debug;
var node10 = process.version.indexOf('v0.10.') === 0;

if (node10) {
  debug = function () {
    if (process.env.NODE_DEBUG && /agentkeepalive/.test(process.env.NODE_DEBUG)) {
      console.log.apply(console.log, arguments);
    }
  };
} else {
  debug = util.debuglog('agentkeepalive');
}

exports.debug = debug;
exports.isNode10 = node10;
exports.inherits = util.inherits;
