'use strict';

var common = require('./common');
var EventEmitter = require('../').EventEmitter;
var once = require('../').once;
var assert = require('assert');

function onceAnEvent() {
  var ee = new EventEmitter();

  process.nextTick(function () {
    ee.emit('myevent', 42);
  });

  return once(ee, 'myevent').then(function (args) {
    var value = args[0]
    assert.strictEqual(value, 42);
    assert.strictEqual(ee.listenerCount('error'), 0);
    assert.strictEqual(ee.listenerCount('myevent'), 0);
  });
}

function onceAnEventWithTwoArgs() {
  var ee = new EventEmitter();

  process.nextTick(function () {
    ee.emit('myevent', 42, 24);
  });

  return once(ee, 'myevent').then(function (value) {
    assert.strictEqual(value.length, 2);
    assert.strictEqual(value[0], 42);
    assert.strictEqual(value[1], 24);
  });
}

function catchesErrors() {
  var ee = new EventEmitter();

  var expected = new Error('kaboom');
  var err;
  process.nextTick(function () {
    ee.emit('error', expected);
  });

  return once(ee, 'myevent').then(function () {
    throw new Error('should reject')
  }, function (err) {
    assert.strictEqual(err, expected);
    assert.strictEqual(ee.listenerCount('error'), 0);
    assert.strictEqual(ee.listenerCount('myevent'), 0);
  });
}

function stopListeningAfterCatchingError() {
  var ee = new EventEmitter();

  var expected = new Error('kaboom');
  var err;
  process.nextTick(function () {
    ee.emit('error', expected);
    ee.emit('myevent', 42, 24);
  });

  // process.on('multipleResolves', common.mustNotCall());

  return once(ee, 'myevent').then(common.mustNotCall, function (err) {
    // process.removeAllListeners('multipleResolves');
    assert.strictEqual(err, expected);
    assert.strictEqual(ee.listenerCount('error'), 0);
    assert.strictEqual(ee.listenerCount('myevent'), 0);
  });
}

function onceError() {
  var ee = new EventEmitter();

  var expected = new Error('kaboom');
  process.nextTick(function () {
    ee.emit('error', expected);
  });

  return once(ee, 'error').then(function (args) {
    var err = args[0]
    assert.strictEqual(err, expected);
    assert.strictEqual(ee.listenerCount('error'), 0);
    assert.strictEqual(ee.listenerCount('myevent'), 0);
  });
}

Promise.all([
  onceAnEvent(),
  onceAnEventWithTwoArgs(),
  catchesErrors(),
  stopListeningAfterCatchingError(),
  onceError()
]).catch(function (err) {
  console.error(err.stack)
  process.exit(1)
});
