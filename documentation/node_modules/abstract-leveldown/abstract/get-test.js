var db
  , verifyNotFoundError = require('./util').verifyNotFoundError
  , isTypedArray        = require('./util').isTypedArray

module.exports.setUp = function (leveldown, test, testCommon) {
  test('setUp common', testCommon.setUp)
  test('setUp db', function (t) {
    db = leveldown(testCommon.location())
    db.open(t.end.bind(t))
  })
}

module.exports.args = function (test) {
  test('test argument-less get() throws', function (t) {
    t.throws(
        db.get.bind(db)
      , { name: 'Error', message: 'get() requires a callback argument' }
      , 'no-arg get() throws'
    )
    t.end()
  })

  test('test callback-less, 1-arg, get() throws', function (t) {
    t.throws(
        db.get.bind(db, 'foo')
      , { name: 'Error', message: 'get() requires a callback argument' }
      , 'callback-less, 1-arg get() throws'
    )
    t.end()
  })

  test('test callback-less, 3-arg, get() throws', function (t) {
    t.throws(
        db.get.bind(db, 'foo', {})
      , { name: 'Error', message: 'get() requires a callback argument' }
      , 'callback-less, 2-arg get() throws'
    )
    t.end()
  })
}

module.exports.get = function (test) {
  test('test simple get()', function (t) {
    db.put('foo', 'bar', function (err) {
      t.notOk(err, 'no error')
      db.get('foo', function (err, value) {
        t.notOk(err, 'no error')
        t.ok(typeof value !== 'string', 'should not be string by default')

        var result
        if (isTypedArray(value)) {
          result = String.fromCharCode.apply(null, new Uint16Array(value))
        } else {
          t.ok(typeof Buffer != 'undefined' && value instanceof Buffer)
          result = value.toString()
        }

        t.equal(result, 'bar')

        db.get('foo', {}, function (err, value) { // same but with {}
          t.notOk(err, 'no error')
          t.ok(typeof value !== 'string', 'should not be string by default')

          var result
          if (isTypedArray(value)) {
            result = String.fromCharCode.apply(null, new Uint16Array(value))
          } else {
            t.ok(typeof Buffer != 'undefined' && value instanceof Buffer)
            result = value.toString()
          }

          t.equal(result, 'bar')

          db.get('foo', { asBuffer: false }, function (err, value) {
            t.notOk(err, 'no error')
            t.ok(typeof value === 'string', 'should be string if not buffer')
            t.equal(value, 'bar')
            t.end()
          })
        })
      })
    })
  })

  test('test simultaniously get()', function (t) {
    db.put('hello', 'world', function (err) {
      t.notOk(err, 'should not error')
      var r = 0
        , done = function () {
            if (++r == 20)
              t.end()
          }
        , i = 0
        , j = 0

      for (; i < 10; ++i)
        db.get('hello', function(err, value) {
          t.notOk(err, 'should not error')
          t.equal(value.toString(), 'world')
          done()
        })

      for (; j < 10; ++j)
        db.get('not found', function(err, value) {
          t.ok(err, 'should error')
          t.ok(verifyNotFoundError(err), 'should have correct error message')
          t.ok(typeof value == 'undefined', 'value is undefined')
          done()
        })
    })
  })
}

module.exports.tearDown = function (test, testCommon) {
  test('tearDown', function (t) {
    db.close(testCommon.tearDown.bind(null, t))
  })
}

module.exports.all = function (leveldown, test, testCommon) {
  module.exports.setUp(leveldown, test, testCommon)
  module.exports.args(test)
  module.exports.get(test)
  module.exports.tearDown(test, testCommon)
}