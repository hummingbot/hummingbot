/**** SETUP & UTILITY STUFF ****/


var db
  , testBuffer
  , test
  , verifyNotFoundError = require('./util').verifyNotFoundError
  , isTypedArray        = require('./util').isTypedArray

function makeGetDelErrorTests (type, key, expectedError) {
  test('test get() with ' + type + ' causes error', function (t) {
    db.get(key, function (err) {
      t.ok(err, 'has error')
      t.ok(err instanceof Error)
      t.ok(err.message.match(expectedError), 'correct error message')
      t.end()
    })
  })

  test('test del() with ' + type + ' causes error', function (t) {
    db.del(key, function (err) {
      t.ok(err, 'has error')
      t.ok(err instanceof Error)
      t.ok(err.message.match(expectedError), 'correct error message')
      t.end()
    })
  })
}

function makePutErrorTest (type, key, value, expectedError) {
  test('test put() with ' + type + ' causes error', function (t) {
    db.put(key, value, function (err) {
      t.ok(err, 'has error')
      t.ok(err instanceof Error)
      t.ok(err.message.match(expectedError), 'correct error message')
      t.end()
    })
  })
}

function makePutGetDelSuccessfulTest (type, key, value) {
  test('test put()/get()/del() with ' + type, function (t) {
    db.put(key, value, function (err) {
      t.notOk(err, 'no error')
      db.get(key, function (err, _value) {
        t.notOk(err, 'no error, has key/value for `' + key + '`')
        t.ok(Buffer.isBuffer(_value), 'is a Buffer')
        var result = _value.toString()
        value = value.toString()
        t.equals(result, value)
        db.del(key, function (err) {
          t.notOk(err, 'no error, deleted key/value for `' + key + '`')
          db.get(key, function (err,  value) {
            t.ok(err, 'entry propertly deleted')
            t.ok(verifyNotFoundError(err), 'should have correct error message')
            t.ok(typeof value == 'undefined', 'value is undefined')
            t.end()
          })
        })
      })
    })
  })
}

function makeErrorKeyTest (type, key, expectedError) {
  makeGetDelErrorTests(type, key, expectedError)
  makePutErrorTest(type, key, 'foo', expectedError)
}

/**** SETUP ENVIRONMENT ****/

module.exports.setUp = function (leveldown, test, testCommon) {
  test('setUp common', testCommon.setUp)
  test('setUp db', function (t) {
    db = leveldown(testCommon.location())
    db.open(t.end.bind(t))
  })
}

/**** TEST ERROR KEYS ****/

module.exports.errorKeys = function (testFunc, BufferType) {
  if (!BufferType) BufferType = Buffer
  test = testFunc
  makeErrorKeyTest('null key', null, /key cannot be `null` or `undefined`/)
  makeErrorKeyTest('undefined key', undefined, /key cannot be `null` or `undefined`/)
  makeErrorKeyTest('empty String key', '', /key cannot be an empty String/)
  makeErrorKeyTest('empty Buffer key', new BufferType(0), /key cannot be an empty \w*Buffer/)
  makeErrorKeyTest('empty Array key', [], /key cannot be an empty String/)
}

/**** TEST NON-ERROR KEYS ****/

module.exports.nonErrorKeys = function (testFunc) {
  // valid falsey keys
  test = testFunc
  makePutGetDelSuccessfulTest('`false` key', false, 'foo false')
  makePutGetDelSuccessfulTest('`0` key', 0, 'foo 0')
  makePutGetDelSuccessfulTest('`NaN` key', NaN, 'foo NaN')

  // standard String key
  makePutGetDelSuccessfulTest(
      'long String key'
    , 'some long string that I\'m using as a key for this unit test, cross your fingers dude, we\'re going in!'
    , 'foo'
  )

  if (!process.browser) {
    // Buffer key
    makePutGetDelSuccessfulTest('Buffer key', testBuffer, 'foo')
  }

  // non-empty Array as a value
  makePutGetDelSuccessfulTest('Array value', 'foo', [1,2,3,4])
}

/**** TEST ERROR VALUES ****/

module.exports.errorValues = function (testFunc, BufferType) {
  if (!BufferType) BufferType = Buffer
  test = testFunc
  makePutErrorTest('null value', 'foo', null, /value cannot be `null` or `undefined`/)
  makePutErrorTest('undefined value', 'foo', undefined, /value cannot be `null` or `undefined`/)
  makePutErrorTest('empty String value', 'foo', '', /value cannot be an empty String/)
  makePutErrorTest('empty Buffer value', 'foo', new BufferType(0), /value cannot be an empty \w*Buffer/)
  makePutErrorTest('empty Array value', 'foo', [], /value cannot be an empty String/)
}

module.exports.nonErrorKeys = function (testFunc) {
  // valid falsey values
  test = testFunc
  makePutGetDelSuccessfulTest('`false` value', 'foo false', false)
  makePutGetDelSuccessfulTest('`0` value', 'foo 0', 0)
  makePutGetDelSuccessfulTest('`NaN` value', 'foo NaN', NaN)

  // standard String value
  makePutGetDelSuccessfulTest(
      'long String value'
    , 'foo'
    , 'some long string that I\'m using as a key for this unit test, cross your fingers dude, we\'re going in!'
  )

  // standard Buffer value
  makePutGetDelSuccessfulTest('Buffer value', 'foo', testBuffer)

  // non-empty Array as a key
  makePutGetDelSuccessfulTest('Array key', [1,2,3,4], 'foo')
}

/**** CLEANUP ENVIRONMENT ****/

module.exports.tearDown = function (test, testCommon) {
  test('tearDown', function (t) {
    db.close(testCommon.tearDown.bind(null, t))
  })
}

module.exports.all = function (leveldown, testFunc, testCommon, buffer, BufferType) {
  testBuffer = buffer
  test = testFunc
  module.exports.setUp(leveldown, test, testCommon)
  module.exports.errorKeys(test, BufferType)
  module.exports.nonErrorKeys(test)
  module.exports.errorValues(test, BufferType)
  module.exports.nonErrorKeys(test)
  module.exports.tearDown(test, testCommon)
}
