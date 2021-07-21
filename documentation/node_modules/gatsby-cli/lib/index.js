#!/usr/bin/env node
"use strict";

require("core-js/modules/es6.typed.array-buffer");

require("core-js/modules/es6.typed.int8-array");

require("core-js/modules/es6.typed.uint8-array");

require("core-js/modules/es6.typed.uint8-clamped-array");

require("core-js/modules/es6.typed.int16-array");

require("core-js/modules/es6.typed.uint16-array");

require("core-js/modules/es6.typed.int32-array");

require("core-js/modules/es6.typed.uint32-array");

require("core-js/modules/es6.typed.float32-array");

require("core-js/modules/es6.typed.float64-array");

require("core-js/modules/es6.map");

require("core-js/modules/es6.set");

require("core-js/modules/es6.weak-map");

require("core-js/modules/es6.weak-set");

require("core-js/modules/es6.reflect.apply");

require("core-js/modules/es6.reflect.construct");

require("core-js/modules/es6.reflect.define-property");

require("core-js/modules/es6.reflect.delete-property");

require("core-js/modules/es6.reflect.get");

require("core-js/modules/es6.reflect.get-own-property-descriptor");

require("core-js/modules/es6.reflect.get-prototype-of");

require("core-js/modules/es6.reflect.has");

require("core-js/modules/es6.reflect.is-extensible");

require("core-js/modules/es6.reflect.own-keys");

require("core-js/modules/es6.reflect.prevent-extensions");

require("core-js/modules/es6.reflect.set");

require("core-js/modules/es6.reflect.set-prototype-of");

require("core-js/modules/es6.promise");

require("core-js/modules/es6.symbol");

require("core-js/modules/es6.function.name");

require("core-js/modules/es6.regexp.flags");

require("core-js/modules/es6.regexp.match");

require("core-js/modules/es6.regexp.replace");

require("core-js/modules/es6.regexp.split");

require("core-js/modules/es6.regexp.search");

require("core-js/modules/es6.array.from");

require("core-js/modules/es7.array.includes");

require("core-js/modules/es7.object.values");

require("core-js/modules/es7.object.entries");

require("core-js/modules/es7.object.get-own-property-descriptors");

require("core-js/modules/es7.string.pad-start");

require("core-js/modules/es7.string.pad-end");

require("regenerator-runtime/runtime");

var createCli = require(`./create-cli`);

// babel-preset-env doesn't find this import if you
// use require() with backtick strings so use the es6 syntax

var report = require(`./reporter`);

global.Promise = require(`bluebird`);

var version = process.version;
var verDigit = Number(version.match(/\d+/)[0]);

var pkg = require(`../package.json`);
var updateNotifier = require(`update-notifier`);
// Check if update is available
updateNotifier({ pkg }).notify();

if (verDigit < 4) {
  report.panic(`Gatsby 1.0+ requires node.js v4 or higher (you have ${version}). \n` + `Upgrade node to the latest stable release.`);
}

Promise.onPossiblyUnhandledRejection(function (error) {
  report.error(error);
  throw error;
});

process.on(`unhandledRejection`, function (error) {
  // This will exit the process in newer Node anyway so lets be consistent
  // across versions and crash
  report.panic(`UNHANDLED REJECTION`, error);
});

process.on(`uncaughtException`, function (error) {
  report.panic(`UNHANDLED EXCEPTION`, error);
});

createCli(process.argv);