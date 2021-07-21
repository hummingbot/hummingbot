'use strict';

var path = require('path');

var libs = new Map();

// our es6 versions
libs.set('process', require.resolve('process-es6'));
libs.set('buffer', require.resolve('buffer-es6'));
libs.set('util', require.resolve(path.join('..', 'src', 'es6', 'util')));
libs.set('sys', libs.get('util'));
libs.set('events', require.resolve(path.join('..', 'src', 'es6', 'events')));
libs.set('stream', require.resolve(path.join('..', 'src', 'es6', 'stream')));
libs.set('path', require.resolve(path.join('..', 'src', 'es6', 'path')));
libs.set('querystring', require.resolve(path.join('..', 'src', 'es6', 'qs')));
libs.set('punycode', require.resolve(path.join('..', 'src', 'es6', 'punycode')));
libs.set('url', require.resolve(path.join('..', 'src', 'es6', 'url')));
libs.set('string_decoder', require.resolve(path.join('..', 'src', 'es6', 'string-decoder')));
libs.set('http', require.resolve(path.join('..', 'src', 'es6', 'http')));
libs.set('https', require.resolve(path.join('..', 'src', 'es6', 'http')));
libs.set('os', require.resolve(path.join('..', 'src', 'es6', 'os')));
libs.set('assert', require.resolve(path.join('..', 'src', 'es6', 'assert')));
libs.set('constants', require.resolve('./constants'));
libs.set('_stream_duplex', require.resolve(path.join('..', 'src', 'es6', 'readable-stream', 'duplex')));
libs.set('_stream_passthrough', require.resolve(path.join('..', 'src', 'es6', 'readable-stream', 'passthrough')));
libs.set('_stream_readable', require.resolve(path.join('..', 'src', 'es6', 'readable-stream', 'readable')));
libs.set('_stream_writable', require.resolve(path.join('..', 'src', 'es6', 'readable-stream', 'writable')));
libs.set('_stream_transform', require.resolve(path.join('..', 'src', 'es6', 'readable-stream', 'transform')));
libs.set('timers', require.resolve(path.join('..', 'src', 'es6', 'timers')));
libs.set('console', require.resolve(path.join('..', 'src', 'es6', 'console')));
libs.set('vm', require.resolve(path.join('..', 'src', 'es6', 'vm')));
libs.set('zlib', require.resolve(path.join('..', 'src', 'es6', 'zlib')));
libs.set('tty', require.resolve(path.join('..', 'src', 'es6', 'tty')));
libs.set('domain', require.resolve(path.join('..', 'src', 'es6', 'domain')));

var CRYPTO_PATH = require.resolve('crypto-browserify');
var FS_PATH = require.resolve('browserify-fs');
var EMPTY_PATH = require.resolve(path.join('..', 'src', 'es6', 'empty'));

// not shimmed
libs.set('dns', EMPTY_PATH);
libs.set('dgram', EMPTY_PATH);
libs.set('child_process', EMPTY_PATH);
libs.set('cluster', EMPTY_PATH);
libs.set('module', EMPTY_PATH);
libs.set('net', EMPTY_PATH);
libs.set('readline', EMPTY_PATH);
libs.set('repl', EMPTY_PATH);
libs.set('tls', EMPTY_PATH);

var index = function (opts) {
  opts = opts || {};
  var cryptoPath = EMPTY_PATH;
  var fsPath = EMPTY_PATH;
  if (opts.crypto) {
    cryptoPath = CRYPTO_PATH;
  }
  if (opts.fs) {
    fsPath = FS_PATH;
  }
  return {
    resolveId: function resolveId(importee) {
      if (importee && importee.slice(-1) === '/') {
        importee === importee.slice(0, -1);
      }
      if (libs.has(importee)) {
        return libs.get(importee);
      }
      if (importee === 'crypto') {
        return cryptoPath;
      }
      if (importee === 'fs') {
        return fsPath;
      }
    }
  };
};

module.exports = index;
