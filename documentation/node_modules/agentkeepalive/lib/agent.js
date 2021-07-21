/**
 * refer:
 *   * @atimb "Real keep-alive HTTP agent": https://gist.github.com/2963672
 *   * https://github.com/joyent/node/blob/master/lib/http.js
 *   * https://github.com/joyent/node/blob/master/lib/https.js
 *   * https://github.com/joyent/node/blob/master/lib/_http_agent.js
 *
 * Copyright(c) 2012 - 2014 fengmk2 <fengmk2@gmail.com>
 * Copyright(c) node-modules
 * MIT Licensed
 */

'use strict';

/**
 * Module dependencies.
 */

var https = require('https');
var utils = require('./utils');
var OriginalAgent = require('./_http_agent').Agent;
var OriginalHttpsAgent = https.Agent;

module.exports = Agent;

function Agent(options) {
  if (!(this instanceof Agent)) {
    return new Agent(options);
  }

  options = options || {};
  options.keepAlive = options.keepAlive !== false;
  // default is keep-alive and 15s free socket timeout
  if (options.keepAliveTimeout === undefined) {
    options.keepAliveTimeout = 15000;
  }
  // default timeout is double keepalive timeout
  if (options.timeout === undefined) {
    options.timeout = options.keepAliveTimeout * 2;
  }

  OriginalAgent.call(this, options);

  var self = this;
  self.createSocketCount = 0;
  self.closeSocketCount = 0;
  // socket error event count
  self.errorSocketCount = 0;
  self.requestCount = 0;
  self.timeoutSocketCount = 0;
  self.on('free', function () {
    self.requestCount++;
  });
  self.on('timeout', function () {
    self.timeoutSocketCount++;
  });
  self.on('close', function () {
    self.closeSocketCount++;
  });
  self.on('error', function () {
    self.errorSocketCount++;
  });
}

utils.inherits(Agent, OriginalAgent);

Agent.prototype.createSocket = function (req, options) {
  var socket = OriginalAgent.prototype.createSocket.call(this, req, options);
  if (this.keepAlive) {
    // Disable Nagle's algorithm: http://blog.caustik.com/2012/04/08/scaling-node-js-to-100k-concurrent-connections/
    // http://fengmk2.com/benchmark/nagle-algorithm-delayed-ack-mock.html
    socket.setNoDelay(true);
  }
  this.createSocketCount++;
  return socket;
};

Agent.prototype.getCurrentStatus = function () {
  return {
    createSocketCount: this.createSocketCount,
    closeSocketCount: this.closeSocketCount,
    errorSocketCount: this.errorSocketCount,
    timeoutSocketCount: this.timeoutSocketCount,
    requestCount: this.requestCount,
    freeSockets: inspect(this.freeSockets),
    sockets: inspect(this.sockets),
    requests: inspect(this.requests)
  };
};

function inspect(obj) {
  var res = {};
  for (var key in obj) {
    res[key] = obj[key].length;
  }
  return res;
}
