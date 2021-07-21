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
  test('test argument-less put() throws', function (t) {
    t.throws(
        db.put.bind(db)
      , { name: 'Error', message: 'put() requires a callback argument' }
      , 'no-arg put() throws'
    )
    t.end()
  })

  test('test callback-less, 1-arg, put() throws', function (t) {
    t.throws(
        db.put.bind(db, 'foo')
      , { name: 'Error', message: 'put() requires a callback argument' }
      , 'callback-less, 1-arg put() throws'
    )
    t.end()
  })

  test('test callback-less, 2-arg, put() throws', function (t) {
    t.throws(
        db.put.bind(db, 'foo', 'bar')
      , { name: 'Error', message: 'put() requires a callback argument' }
      , 'callback-less, 2-arg put() throws'
    )
    t.end()
  })

  test('test callback-less, 3-arg, put() throws', function (t) {
    t.throws(
        db.put.bind(db, 'foo', 'bar', {})
      , { name: 'Error', message: 'put() requires a callback argument' }
      , 'callback-less, 3-arg put() throws'
    )
    t.end()
  })
}

module.exports.put = function (test) {
  test('test simple put()', function (t) {
    db.put('foo', 'bar', function (err) {
      t.notOk(err, 'no error')
      db.get('foo', function (err, value) {
        t.notOk(err, 'no error')
        var result = value.toString()
        if (isTypedArray(value))
          result = String.fromCharCode.apply(null, new Uint16Array(value))
        t.equal(result, 'bar')
        t.end()
      })
    })
  })
  
  if (process.browser) {
    test('test object value put()', function (t) {
      db.put('dood', {pete: 'sampras'}, function (err) {
        t.notOk(err, 'no error')
        db.get('dood', { asBuffer: false }, function (err, value) {
          t.notOk(err, 'no error')
          t.equal(JSON.stringify(value), JSON.stringify({pete: 'sampras'}))
          t.end()
        })
      })
    })
  }

}

module.exports.tearDown = function (test, testCommon) {
  test('tearDown', function (t) {
    db.close(testCommon.tearDown.bind(null, t))
  })
}

module.exports.all = function (leveldown, test, testCommon) {
  module.exports.setUp(leveldown, test, testCommon)
  module.exports.args(test)
  module.exports.put(test)
  module.exports.tearDown(test, testCommon)
}