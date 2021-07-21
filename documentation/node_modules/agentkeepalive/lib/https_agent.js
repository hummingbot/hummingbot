/**
 * Https Agent base on custom http agent
 *
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

var https = require('https');
var utils = require('./utils');
var HttpAgent = require('./agent');
var OriginalHttpsAgent = https.Agent;

var HttpsAgent;

if (utils.isNode10) {
  // node v0.10
  HttpsAgent = function HttpsAgent(options) {
    HttpAgent.call(this, options);
    this.defaultPort = 443;
    this.protocol = 'https:';
  };

  utils.inherits(HttpsAgent, HttpAgent);

  HttpsAgent.prototype.createConnection = https.globalAgent.createConnection;
  HttpsAgent.prototype.getName = function(options) {
    var name = HttpAgent.prototype.getName.call(this, options);

    name += ':';
    if (options.ca)
      name += options.ca;

    name += ':';
    if (options.cert)
      name += options.cert;

    name += ':';
    if (options.ciphers)
      name += options.ciphers;

    name += ':';
    if (options.key)
      name += options.key;

    name += ':';
    if (options.pfx)
      name += options.pfx;

    name += ':';
    if (options.rejectUnauthorized !== undefined)
      name += options.rejectUnauthorized;

    return name;
  };
} else {
  HttpsAgent = function HttpsAgent(options) {
    HttpAgent.call(this, options);
    this.defaultPort = 443;
    this.protocol = 'https:';
    this.maxCachedSessions = this.options.maxCachedSessions;
    if (this.maxCachedSessions === undefined)
      this.maxCachedSessions = 100;

    this._sessionCache = {
      map: {},
      list: []
    };
  };

  utils.inherits(HttpsAgent, HttpAgent);

  [
    'createConnection',
    'getName',
    '_getSession',
    '_cacheSession',
    // https://github.com/nodejs/node/pull/4982
    '_evictSession',
  ].forEach(function(method) {
    if (typeof OriginalHttpsAgent.prototype[method] === 'function') {
      HttpsAgent.prototype[method] = OriginalHttpsAgent.prototype[method];
    }
  });
}

module.exports = HttpsAgent;
