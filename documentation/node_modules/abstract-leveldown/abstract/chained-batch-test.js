var db

module.exports.setUp = function (leveldown, test, testCommon) {
  test('setUp common', testCommon.setUp)
  test('setUp db', function (t) {
    db = leveldown(testCommon.location())
    db.open(t.end.bind(t))
  })
}

module.exports.args = function (test) {
  test('test batch#put() with missing `value`', function (t) {
    try {
      db.batch().put('foo1')
    } catch (err) {
      t.equal(err.message, 'value cannot be `null` or `undefined`', 'correct error message')
      return t.end()
    }
    t.fail('should have thrown')
    t.end()
  })

  test('test batch#put() with null `value`', function (t) {
    try {
      db.batch().put('foo1', null)
    } catch (err) {
      t.equal(err.message, 'value cannot be `null` or `undefined`', 'correct error message')
      return t.end()
    }
    t.fail('should have thrown')
    t.end()
  })

  test('test batch#put() with missing `key`', function (t) {
    try {
      db.batch().put(undefined, 'foo1')
    } catch (err) {
      t.equal(err.message, 'key cannot be `null` or `undefined`', 'correct error message')
      return t.end()
    }
    t.fail('should have thrown')
    t.end()
  })

  test('test batch#put() with null `key`', function (t) {
    try {
      db.batch().put(null, 'foo1')
    } catch (err) {
      t.equal(err.message, 'key cannot be `null` or `undefined`', 'correct error message')
      return t.end()
    }
    t.fail('should have thrown')
    t.end()
  })

  test('test batch#put() with missing `key` and `value`', function (t) {
    try {
      db.batch().put()
    } catch (err) {
      t.equal(err.message, 'key cannot be `null` or `undefined`', 'correct error message')
      return t.end()
    }
    t.fail('should have thrown')
    t.end()
  })

  test('test batch#del() with missing `key`', function (t) {
    try {
      db.batch().del()
    } catch (err) {
      t.equal(err.message, 'key cannot be `null` or `undefined`', 'correct error message')
      return t.end()
    }
    t.fail('should have thrown')
    t.end()
  })

  test('test batch#del() with null `key`', function (t) {
    try {
      db.batch().del(null)
    } catch (err) {
      t.equal(err.message, 'key cannot be `null` or `undefined`', 'correct error message')
      return t.end()
    }
    t.fail('should have thrown')
    t.end()
  })

  test('test batch#del() with null `key`', function (t) {
    try {
      db.batch().del(null)
    } catch (err) {
      t.equal(err.message, 'key cannot be `null` or `undefined`', 'correct error message')
      return t.end()
    }
    t.fail('should have thrown')
    t.end()
  })

  test('test batch#clear() doesn\'t throw', function (t) {
    db.batch().clear()
    t.end()
  })

  test('test batch#write() with no callback', function (t) {
    try {
      db.batch().write()
    } catch (err) {
      t.equal(err.message, 'write() requires a callback argument', 'correct error message')
      return t.end()
    }
    t.fail('should have thrown')
    t.end()
  })

  test('test batch#put() after write()', function (t) {
    var batch = db.batch().put('foo', 'bar')
    batch.write(function () {})
    try {
      batch.put('boom', 'bang')
    } catch (err) {
      t.equal(err.message, 'write() already called on this batch', 'correct error message')
      return t.end()
    }
    t.fail('should have thrown')
    t.end()
  })

  test('test batch#del() after write()', function (t) {
    var batch = db.batch().put('foo', 'bar')
    batch.write(function () {})
    try {
      batch.del('foo')
    } catch (err) {
      t.equal(err.message, 'write() already called on this batch', 'correct error message')
      return t.end()
    }
    t.fail('should have thrown')
    t.end()
  })

  test('test batch#clear() after write()', function (t) {
    var batch = db.batch().put('foo', 'bar')
    batch.write(function () {})
    try {
      batch.clear()
    } catch (err) {
      t.equal(err.message, 'write() already called on this batch', 'correct error message')
      return t.end()
    }
    t.fail('should have thrown')
    t.end()
  })

  test('test batch#write() after write()', function (t) {
    var batch = db.batch().put('foo', 'bar')
    batch.write(function () {})
    try {
      batch.write(function (err) {})
    } catch (err) {
      t.equal(err.message, 'write() already called on this batch', 'correct error message')
      return t.end()
    }
    t.fail('should have thrown')
    t.end()
  })
}

module.exports.batch = function (test, testCommon) {
  test('test basic batch', function (t) {
    db.batch(
        [
            { type: 'put', key: 'one', value: '1' }
          , { type: 'put', key: 'two', value: '2' }
          , { type: 'put', key: 'three', value: '3' }
        ]
      , function (err) {
          t.notOk(err, 'no error')

          db.batch()
            .put('1', 'one')
            .del('2', 'two')
            .put('3', 'three')
            .clear()
            .put('one', 'I')
            .put('two', 'II')
            .del('three')
            .put('foo', 'bar')
            .write(function (err) {
              t.notOk(err, 'no error')
              testCommon.collectEntries(
                  db.iterator({ keyAsBuffer: false, valueAsBuffer: false })
                , function (err, data) {
                    t.notOk(err, 'no error')
                    t.equal(data.length, 3, 'correct number of entries')
                    var expected = [
                        { key: 'foo', value: 'bar' }
                      , { key: 'one', value: 'I' }
                      , { key: 'two', value: 'II' }
                    ]
                    t.deepEqual(data, expected)
                    t.end()
                  }
              )
            })
        }
    )
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
  module.exports.batch(test, testCommon)
  module.exports.tearDown(test, testCommon)
}