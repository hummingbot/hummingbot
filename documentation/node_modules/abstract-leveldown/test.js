const tap                  = require('tap')
    , sinon                = require('sinon')
    , util                 = require('util')
    , testCommon           = require('./testCommon')
    , AbstractLevelDOWN    = require('./').AbstractLevelDOWN
    , AbstractIterator     = require('./').AbstractIterator
    , AbstractChainedBatch = require('./').AbstractChainedBatch

function factory (location) {
  return new AbstractLevelDOWN(location)
}

/*** compatibility with basic LevelDOWN API ***/

require('./abstract/leveldown-test').args(factory, tap.test, testCommon)

require('./abstract/open-test').args(factory, tap.test, testCommon)

require('./abstract/del-test').setUp(factory, tap.test, testCommon)
require('./abstract/del-test').args(tap.test)

require('./abstract/get-test').setUp(factory, tap.test, testCommon)
require('./abstract/get-test').args(tap.test)

require('./abstract/put-test').setUp(factory, tap.test, testCommon)
require('./abstract/put-test').args(tap.test)

require('./abstract/put-get-del-test').setUp(factory, tap.test, testCommon)
require('./abstract/put-get-del-test').errorKeys(tap.test)
//require('./abstract/put-get-del-test').nonErrorKeys(tap.test, testCommon)
require('./abstract/put-get-del-test').errorValues(tap.test)
//require('./abstract/test/put-get-del-test').nonErrorKeys(tap.test, testCommon)
require('./abstract/put-get-del-test').tearDown(tap.test, testCommon)

require('./abstract/approximate-size-test').setUp(factory, tap.test, testCommon)
require('./abstract/approximate-size-test').args(tap.test)

require('./abstract/batch-test').setUp(factory, tap.test, testCommon)
require('./abstract/batch-test').args(tap.test)

require('./abstract/chained-batch-test').setUp(factory, tap.test, testCommon)
require('./abstract/chained-batch-test').args(tap.test)

require('./abstract/close-test').close(factory, tap.test, testCommon)

require('./abstract/iterator-test').setUp(factory, tap.test, testCommon)
require('./abstract/iterator-test').args(tap.test)
require('./abstract/iterator-test').sequence(tap.test)

/*** extensibility ***/

tap.test('test core extensibility', function (t) {
  function Test (location) {
    AbstractLevelDOWN.call(this, location)
    t.equal(this.location, location, 'location set on `this`')
    t.end()
  }

  util.inherits(Test, AbstractLevelDOWN)

  ;new Test('foobar')
})

tap.test('test open() extensibility', function (t) {
  var spy = sinon.spy()
    , expectedCb = function () {}
    , expectedOptions = { options: 1 }
    , test

  function Test (location) {
    AbstractLevelDOWN.call(this, location)
  }

  util.inherits(Test, AbstractLevelDOWN)

  Test.prototype._open = spy

  test = new Test('foobar')
  test.open(expectedCb)

  t.equal(spy.callCount, 1, 'got _open() call')
  t.equal(spy.getCall(0).thisValue, test, '`this` on _open() was correct')
  t.equal(spy.getCall(0).args.length, 2, 'got two arguments')
  t.deepEqual(spy.getCall(0).args[0], {}, 'got blank options argument')
  t.equal(spy.getCall(0).args[1], expectedCb, 'got expected cb argument')

  test.open(expectedOptions, expectedCb)

  t.equal(spy.callCount, 2, 'got _open() call')
  t.equal(spy.getCall(1).thisValue, test, '`this` on _open() was correct')
  t.equal(spy.getCall(1).args.length, 2, 'got two arguments')
  t.deepEqual(spy.getCall(1).args[0], expectedOptions, 'got blank options argument')
  t.equal(spy.getCall(1).args[1], expectedCb, 'got expected cb argument')
  t.end()
})

tap.test('test close() extensibility', function (t) {
  var spy = sinon.spy()
    , expectedCb = function () {}
    , test

  function Test (location) {
    AbstractLevelDOWN.call(this, location)
  }

  util.inherits(Test, AbstractLevelDOWN)

  Test.prototype._close = spy

  test = new Test('foobar')
  test.close(expectedCb)

  t.equal(spy.callCount, 1, 'got _close() call')
  t.equal(spy.getCall(0).thisValue, test, '`this` on _close() was correct')
  t.equal(spy.getCall(0).args.length, 1, 'got one arguments')
  t.equal(spy.getCall(0).args[0], expectedCb, 'got expected cb argument')
  t.end()
})

tap.test('test get() extensibility', function (t) {
  var spy = sinon.spy()
    , expectedCb = function () {}
    , expectedOptions = { options: 1 }
    , expectedKey = 'a key'
    , test

  function Test (location) {
    AbstractLevelDOWN.call(this, location)
  }

  util.inherits(Test, AbstractLevelDOWN)

  Test.prototype._get = spy

  test = new Test('foobar')
  test.get(expectedKey, expectedCb)

  t.equal(spy.callCount, 1, 'got _get() call')
  t.equal(spy.getCall(0).thisValue, test, '`this` on _get() was correct')
  t.equal(spy.getCall(0).args.length, 3, 'got three arguments')
  t.equal(spy.getCall(0).args[0], expectedKey, 'got expected key argument')
  t.deepEqual(spy.getCall(0).args[1], {}, 'got blank options argument')
  t.equal(spy.getCall(0).args[2], expectedCb, 'got expected cb argument')

  test.get(expectedKey, expectedOptions, expectedCb)

  t.equal(spy.callCount, 2, 'got _get() call')
  t.equal(spy.getCall(1).thisValue, test, '`this` on _get() was correct')
  t.equal(spy.getCall(1).args.length, 3, 'got three arguments')
  t.equal(spy.getCall(1).args[0], expectedKey, 'got expected key argument')
  t.deepEqual(spy.getCall(1).args[1], expectedOptions, 'got blank options argument')
  t.equal(spy.getCall(1).args[2], expectedCb, 'got expected cb argument')
  t.end()
})

tap.test('test del() extensibility', function (t) {
  var spy = sinon.spy()
    , expectedCb = function () {}
    , expectedOptions = { options: 1 }
    , expectedKey = 'a key'
    , test

  function Test (location) {
    AbstractLevelDOWN.call(this, location)
  }

  util.inherits(Test, AbstractLevelDOWN)

  Test.prototype._del = spy

  test = new Test('foobar')
  test.del(expectedKey, expectedCb)

  t.equal(spy.callCount, 1, 'got _del() call')
  t.equal(spy.getCall(0).thisValue, test, '`this` on _del() was correct')
  t.equal(spy.getCall(0).args.length, 3, 'got three arguments')
  t.equal(spy.getCall(0).args[0], expectedKey, 'got expected key argument')
  t.deepEqual(spy.getCall(0).args[1], {}, 'got blank options argument')
  t.equal(spy.getCall(0).args[2], expectedCb, 'got expected cb argument')

  test.del(expectedKey, expectedOptions, expectedCb)

  t.equal(spy.callCount, 2, 'got _del() call')
  t.equal(spy.getCall(1).thisValue, test, '`this` on _del() was correct')
  t.equal(spy.getCall(1).args.length, 3, 'got three arguments')
  t.equal(spy.getCall(1).args[0], expectedKey, 'got expected key argument')
  t.deepEqual(spy.getCall(1).args[1], expectedOptions, 'got blank options argument')
  t.equal(spy.getCall(1).args[2], expectedCb, 'got expected cb argument')
  t.end()
})

tap.test('test put() extensibility', function (t) {
  var spy = sinon.spy()
    , expectedCb = function () {}
    , expectedOptions = { options: 1 }
    , expectedKey = 'a key'
    , expectedValue = 'a value'
    , test

  function Test (location) {
    AbstractLevelDOWN.call(this, location)
  }

  util.inherits(Test, AbstractLevelDOWN)

  Test.prototype._put = spy

  test = new Test('foobar')
  test.put(expectedKey, expectedValue, expectedCb)

  t.equal(spy.callCount, 1, 'got _put() call')
  t.equal(spy.getCall(0).thisValue, test, '`this` on _put() was correct')
  t.equal(spy.getCall(0).args.length, 4, 'got four arguments')
  t.equal(spy.getCall(0).args[0], expectedKey, 'got expected key argument')
  t.equal(spy.getCall(0).args[1], expectedValue, 'got expected value argument')
  t.deepEqual(spy.getCall(0).args[2], {}, 'got blank options argument')
  t.equal(spy.getCall(0).args[3], expectedCb, 'got expected cb argument')

  test.put(expectedKey, expectedValue, expectedOptions, expectedCb)

  t.equal(spy.callCount, 2, 'got _put() call')
  t.equal(spy.getCall(1).thisValue, test, '`this` on _put() was correct')
  t.equal(spy.getCall(1).args.length, 4, 'got four arguments')
  t.equal(spy.getCall(1).args[0], expectedKey, 'got expected key argument')
  t.equal(spy.getCall(1).args[1], expectedValue, 'got expected value argument')
  t.deepEqual(spy.getCall(1).args[2], expectedOptions, 'got blank options argument')
  t.equal(spy.getCall(1).args[3], expectedCb, 'got expected cb argument')
  t.end()
})

tap.test('test approximateSize() extensibility', function (t) {
  var spy = sinon.spy()
    , expectedCb = function () {}
    , expectedStart = 'a start'
    , expectedEnd = 'an end'
    , test

  function Test (location) {
    AbstractLevelDOWN.call(this, location)
  }

  util.inherits(Test, AbstractLevelDOWN)

  Test.prototype._approximateSize = spy

  test = new Test('foobar')
  test.approximateSize(expectedStart, expectedEnd, expectedCb)

  t.equal(spy.callCount, 1, 'got _approximateSize() call')
  t.equal(spy.getCall(0).thisValue, test, '`this` on _approximateSize() was correct')
  t.equal(spy.getCall(0).args.length, 3, 'got three arguments')
  t.equal(spy.getCall(0).args[0], expectedStart, 'got expected start argument')
  t.equal(spy.getCall(0).args[1], expectedEnd, 'got expected end argument')
  t.equal(spy.getCall(0).args[2], expectedCb, 'got expected cb argument')
  t.end()
})

tap.test('test batch() extensibility', function (t) {
  var spy = sinon.spy()
    , expectedCb = function () {}
    , expectedOptions = { options: 1 }
    , expectedArray = [ 1, 2 ]
    , test

  function Test (location) {
    AbstractLevelDOWN.call(this, location)
  }

  util.inherits(Test, AbstractLevelDOWN)

  Test.prototype._batch = spy

  test = new Test('foobar')

  test.batch(expectedArray, expectedCb)

  t.equal(spy.callCount, 1, 'got _batch() call')
  t.equal(spy.getCall(0).thisValue, test, '`this` on _batch() was correct')
  t.equal(spy.getCall(0).args.length, 3, 'got three arguments')
  t.equal(spy.getCall(0).args[0], expectedArray, 'got expected array argument')
  t.deepEqual(spy.getCall(0).args[1], {}, 'got expected options argument')
  t.equal(spy.getCall(0).args[2], expectedCb, 'got expected callback argument')

  test.batch(expectedArray, expectedOptions, expectedCb)

  t.equal(spy.callCount, 2, 'got _batch() call')
  t.equal(spy.getCall(1).thisValue, test, '`this` on _batch() was correct')
  t.equal(spy.getCall(1).args.length, 3, 'got three arguments')
  t.equal(spy.getCall(1).args[0], expectedArray, 'got expected array argument')
  t.deepEqual(spy.getCall(1).args[1], expectedOptions, 'got expected options argument')
  t.equal(spy.getCall(1).args[2], expectedCb, 'got expected callback argument')

  t.end()
})

tap.test('test chained batch() (array) extensibility', function (t) {
  var spy = sinon.spy()
    , expectedCb = function () {}
    , expectedOptions = { options: 1 }
    , expectedArray = [ 1, 2 ]
    , test

  function Test (location) {
    AbstractLevelDOWN.call(this, location)
  }

  util.inherits(Test, AbstractLevelDOWN)

  Test.prototype._batch = spy

  test = new Test('foobar')

  test.batch().put('foo', 'bar').del('bang').write(expectedCb)

  t.equal(spy.callCount, 1, 'got _batch() call')
  t.equal(spy.getCall(0).thisValue, test, '`this` on _batch() was correct')
  t.equal(spy.getCall(0).args.length, 3, 'got three arguments')
  t.equal(spy.getCall(0).args[0].length, 2, 'got expected array argument')
  t.deepEqual(spy.getCall(0).args[0][0], { type: 'put', key: 'foo', value: 'bar' }, 'got expected array argument[0]')
  t.deepEqual(spy.getCall(0).args[0][1], { type: 'del', key: 'bang' }, 'got expected array argument[1]')
  t.deepEqual(spy.getCall(0).args[1], {}, 'got expected options argument')
  t.equal(spy.getCall(0).args[2], expectedCb, 'got expected callback argument')

  test.batch().put('foo', 'bar').del('bang').write(expectedOptions, expectedCb)

  t.equal(spy.callCount, 2, 'got _batch() call')
  t.equal(spy.getCall(1).thisValue, test, '`this` on _batch() was correct')
  t.equal(spy.getCall(1).args.length, 3, 'got three arguments')
  t.equal(spy.getCall(1).args[0].length, 2, 'got expected array argument')
  t.deepEqual(spy.getCall(1).args[0][0], { type: 'put', key: 'foo', value: 'bar' }, 'got expected array argument[0]')
  t.deepEqual(spy.getCall(1).args[0][1], { type: 'del', key: 'bang' }, 'got expected array argument[1]')
  t.deepEqual(spy.getCall(1).args[1], expectedOptions, 'got expected options argument')
  t.equal(spy.getCall(1).args[2], expectedCb, 'got expected callback argument')

  t.end()
})

tap.test('test chained batch() (custom _chainedBatch) extensibility', function (t) {
  var spy = sinon.spy()
    , test

  function Test (location) {
    AbstractLevelDOWN.call(this, location)
  }

  util.inherits(Test, AbstractLevelDOWN)

  Test.prototype._chainedBatch = spy

  test = new Test('foobar')

  test.batch()

  t.equal(spy.callCount, 1, 'got _chainedBatch() call')
  t.equal(spy.getCall(0).thisValue, test, '`this` on _chainedBatch() was correct')

  test.batch()

  t.equal(spy.callCount, 2, 'got _chainedBatch() call')
  t.equal(spy.getCall(1).thisValue, test, '`this` on _chainedBatch() was correct')

  t.end()
})

tap.test('test AbstractChainedBatch extensibility', function (t) {
  function Test (db) {
    AbstractChainedBatch.call(this, db)
    t.equal(this._db, db, 'db set on `this`')
    t.end()
  }

  util.inherits(Test, AbstractChainedBatch)

  new Test('foobar')
})

tap.test('test write() extensibility', function (t) {
  var spy = sinon.spy()
    , spycb = sinon.spy()
    , test

  function Test (db) {
    AbstractChainedBatch.call(this, db)
  }

  util.inherits(Test, AbstractChainedBatch)

  Test.prototype._write = spy

  test = new Test('foobar')
  test.write(spycb)

  t.equal(spy.callCount, 1, 'got _write() call')
  t.equal(spy.getCall(0).thisValue, test, '`this` on _write() was correct')
  t.equal(spy.getCall(0).args.length, 1, 'got one argument')
  // awkward here cause of nextTick & an internal wrapped cb
  t.type(spy.getCall(0).args[0], 'function', 'got a callback function')
  t.equal(spycb.callCount, 0, 'spycb not called')
  spy.getCall(0).args[0]()
  t.equal(spycb.callCount, 1, 'spycb called, i.e. was our cb argument')
  t.end()
})

tap.test('test put() extensibility', function (t) {
  var spy = sinon.spy()
    , expectedKey = 'key'
    , expectedValue = 'value'
    , returnValue
    , test

  function Test (db) {
    AbstractChainedBatch.call(this, db)
  }

  util.inherits(Test, AbstractChainedBatch)

  Test.prototype._put = spy

  test = new Test(factory('foobar'))
  returnValue = test.put(expectedKey, expectedValue)
  t.equal(spy.callCount, 1, 'got _put call')
  t.equal(spy.getCall(0).thisValue, test, '`this` on _put() was correct')
  t.equal(spy.getCall(0).args.length, 2, 'got two arguments')
  t.equal(spy.getCall(0).args[0], expectedKey, 'got expected key argument')
  t.equal(spy.getCall(0).args[1], expectedValue, 'got expected value argument')
  t.equal(returnValue, test, 'get expected return value')
  t.end()
})

tap.test('test del() extensibility', function (t) {
  var spy = sinon.spy()
    , expectedKey = 'key'
    , returnValue
    , test

  function Test (db) {
    AbstractChainedBatch.call(this, db)
  }

  util.inherits(Test, AbstractChainedBatch)

  Test.prototype._del = spy

  test = new Test(factory('foobar'))
  returnValue = test.del(expectedKey)
  t.equal(spy.callCount, 1, 'got _del call')
  t.equal(spy.getCall(0).thisValue, test, '`this` on _del() was correct')
  t.equal(spy.getCall(0).args.length, 1, 'got one argument')
  t.equal(spy.getCall(0).args[0], expectedKey, 'got expected key argument')
  t.equal(returnValue, test, 'get expected return value')
  t.end()
})

tap.test('test clear() extensibility', function (t) {
  var spy = sinon.spy()
    , returnValue
    , test

  function Test (db) {
    AbstractChainedBatch.call(this, db)
  }

  util.inherits(Test, AbstractChainedBatch)

  Test.prototype._clear = spy

  test = new Test(factory('foobar'))
  returnValue = test.clear()
  t.equal(spy.callCount, 1, 'got _clear call')
  t.equal(spy.getCall(0).thisValue, test, '`this` on _clear() was correct')
  t.equal(spy.getCall(0).args.length, 0, 'got zero arguments')
  t.equal(returnValue, test, 'get expected return value')
  t.end()
})

tap.test('test iterator() extensibility', function (t) {
  var spy = sinon.spy()
    , expectedOptions = { options: 1, reverse: false } // reverse now explicitly set
    , test

  function Test (location) {
    AbstractLevelDOWN.call(this, location)
  }

  util.inherits(Test, AbstractLevelDOWN)

  Test.prototype._iterator = spy

  test = new Test('foobar')
  test.iterator({ options: 1 })

  t.equal(spy.callCount, 1, 'got _close() call')
  t.equal(spy.getCall(0).thisValue, test, '`this` on _close() was correct')
  t.equal(spy.getCall(0).args.length, 1, 'got one arguments')
  t.deepEqual(spy.getCall(0).args[0], expectedOptions, 'got expected options argument')
  t.end()
})

tap.test('test AbstractIterator extensibility', function (t) {
  function Test (db) {
    AbstractIterator.call(this, db)
    t.equal(this.db, db, 'db set on `this`')
    t.end()
  }

  util.inherits(Test, AbstractIterator)

  ;new Test('foobar')
})

tap.test('test next() extensibility', function (t) {
  var spy = sinon.spy()
    , spycb = sinon.spy()
    , test

  function Test (db) {
    AbstractIterator.call(this, db)
  }

  util.inherits(Test, AbstractIterator)

  Test.prototype._next = spy

  test = new Test('foobar')
  test.next(spycb)

  t.equal(spy.callCount, 1, 'got _next() call')
  t.equal(spy.getCall(0).thisValue, test, '`this` on _next() was correct')
  t.equal(spy.getCall(0).args.length, 1, 'got one arguments')
  // awkward here cause of nextTick & an internal wrapped cb
  t.type(spy.getCall(0).args[0], 'function', 'got a callback function')
  t.equal(spycb.callCount, 0, 'spycb not called')
  spy.getCall(0).args[0]()
  t.equal(spycb.callCount, 1, 'spycb called, i.e. was our cb argument')
  t.end()
})

tap.test('test end() extensibility', function (t) {
  var spy = sinon.spy()
    , expectedCb = function () {}
    , test

  function Test (db) {
    AbstractIterator.call(this, db)
  }

  util.inherits(Test, AbstractIterator)

  Test.prototype._end = spy

  test = new Test('foobar')
  test.end(expectedCb)

  t.equal(spy.callCount, 1, 'got _end() call')
  t.equal(spy.getCall(0).thisValue, test, '`this` on _end() was correct')
  t.equal(spy.getCall(0).args.length, 1, 'got one arguments')
  t.equal(spy.getCall(0).args[0], expectedCb, 'got expected cb argument')
  t.end()
})
