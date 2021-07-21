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
  test('test callback-less, 2-arg, batch() throws', function (t) {
    t.throws(db.batch.bind(db, 'foo', {}), 'callback-less, 2-arg batch() throws')
    t.end()
  })

  test('test batch() with missing `value`', function (t) {
    db.batch([{ type: 'put', key: 'foo1' }], function (err) {
      t.equal(err.message, 'value cannot be `null` or `undefined`', 'correct error message')
      t.end()
    })
  })

  test('test batch() with null `value`', function (t) {
    db.batch([{ type: 'put', key: 'foo1', value: null }], function (err) {
      t.equal(err.message, 'value cannot be `null` or `undefined`', 'correct error message')
      t.end()
    })
  })

  test('test batch() with missing `key`', function (t) {
    db.batch([{ type: 'put', value: 'foo1' }], function (err) {
      t.equal(err.message, 'key cannot be `null` or `undefined`', 'correct error message')
      t.end()
    })
  })

  test('test batch() with null `key`', function (t) {
    db.batch([{ type: 'put', key: null, value: 'foo1' }], function (err) {
      t.equal(err.message, 'key cannot be `null` or `undefined`', 'correct error message')
      t.end()
    })
  })

  test('test batch() with missing `key` and `value`', function (t) {
    db.batch([{ type: 'put' }], function (err) {
      t.equal(err.message, 'key cannot be `null` or `undefined`', 'correct error message')
      t.end()
    })
  })
}

module.exports.batch = function (test) {
  test('test batch() with empty array', function (t) {
    db.batch([], function (err) {
      t.notOk(err, 'no error')
      t.end()
    })
  })

  test('test simple batch()', function (t) {
    db.batch([{ type: 'put', key: 'foo', value: 'bar' }], function (err) {
      t.notOk(err, 'no error')

      db.get('foo', function (err, value) {
        t.notOk(err, 'no error')
        var result
        if (isTypedArray(value)) {
          result = String.fromCharCode.apply(null, new Uint16Array(value))
        } else {
          t.ok(typeof Buffer != 'undefined' && value instanceof Buffer)
          result = value.toString()
        }
        t.equal(result, 'bar')
        t.end()
      })
    })
  })

  test('test multiple batch()', function (t) {
    db.batch([
        { type: 'put', key: 'foobatch1', value: 'bar1' }
      , { type: 'put', key: 'foobatch2', value: 'bar2' }
      , { type: 'put', key: 'foobatch3', value: 'bar3' }
      , { type: 'del', key: 'foobatch2' }
    ], function (err) {
      t.notOk(err, 'no error')

      var r = 0
        , done = function () {
            if (++r == 3)
              t.end()
          }

      db.get('foobatch1', function (err, value) {
        t.notOk(err, 'no error')
        var result
        if (isTypedArray(value)) {
          result = String.fromCharCode.apply(null, new Uint16Array(value))
        } else {
          t.ok(typeof Buffer != 'undefined' && value instanceof Buffer)
          result = value.toString()
        }
        t.equal(result, 'bar1')
        done()
      })

      db.get('foobatch2', function (err, value) {
        t.ok(err, 'entry not found')
        t.ok(typeof value == 'undefined', 'value is undefined')
        t.ok(verifyNotFoundError(err), 'NotFound error')
        done()
      })

      db.get('foobatch3', function (err, value) {
        t.notOk(err, 'no error')
        var result
        if (isTypedArray(value)) {
          result = String.fromCharCode.apply(null, new Uint16Array(value))
        } else {
          t.ok(typeof Buffer != 'undefined' && value instanceof Buffer)
          result = value.toString()
        }
        t.equal(result, 'bar3')
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
  module.exports.batch(test)
  module.exports.tearDown(test, testCommon)
}
