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
  test('test argument-less del() throws', function (t) {
    t.throws(
        db.del.bind(db)
      , { name: 'Error', message: 'del() requires a callback argument' }
      , 'no-arg del() throws'
    )
    t.end()
  })

  test('test callback-less, 1-arg, del() throws', function (t) {
    t.throws(
        db.del.bind(db, 'foo')
      , { name: 'Error', message: 'del() requires a callback argument' }
      , 'callback-less, 1-arg del() throws'
    )
    t.end()
  })

  test('test callback-less, 3-arg, del() throws', function (t) {
    t.throws(
        db.del.bind(db, 'foo', {})
      , { name: 'Error', message: 'del() requires a callback argument' }
      , 'callback-less, 2-arg del() throws'
    )
    t.end()
  })
}

module.exports.del = function (test) {
  test('test simple del()', function (t) {
    db.put('foo', 'bar', function (err) {
      t.notOk(err, 'no error')
      db.del('foo', function (err) {
        t.notOk(err, 'no error')
        db.get('foo', function (err) {
          t.ok(err, 'entry propertly deleted')
          t.ok(typeof value == 'undefined', 'value is undefined')
          t.ok(verifyNotFoundError(err), 'NotFound error')
          t.end()
        })
      })
    })
  })

  test('test del on non-existent key', function (t) {
    db.del('blargh', function (err) {
      t.notOk(err, 'should not error on delete')
      t.end()
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
  module.exports.del(test)
  module.exports.tearDown(test, testCommon)
}
