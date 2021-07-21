var dbidx = 0
  , leveljs = require('../')
  , location = function () {
      return '_leveldown_test_db_' + dbidx++
    }

  , lastLocation = function () {
      return '_leveldown_test_db_' + dbidx
    }

  , cleanup = function (callback) {
      var list = []
      if (dbidx === 0) return callback()
      for (var i = 0; i < dbidx; i++) {
        list.push('_leveldown_test_db_' + i)
      }
      
      function destroy() {
        var f = list.pop()
        if (list.length === 0) return callback()
        leveljs.destroy(f, destroy)
      }
      
      destroy()
    }

  , setUp = function (t) {
      cleanup(function (err) {
        t.notOk(err, 'cleanup returned an error')
        t.end()
      })
    }

  , tearDown = function (t) {
      setUp(t) // same cleanup!
    }

  , collectEntries = function (iterator, callback) {
      var data = []
        , next = function () {
            iterator.next(function (err, key, value) {
              if (err) return callback(err)
              if (!arguments.length) {
                return iterator.end(function (err) {
                  callback(err, data)
                })
              }
              data.push({ key: key, value: value })
              process.nextTick(next)
            })
          }
      next()
    }

  , makeExistingDbTest = function (name, test, leveldown, testFn) {
      test(name, function (t) {
        cleanup(function () {
          var loc  = location()
            , db   = leveldown(loc)
            , done = function (close) {
                if (close === false)
                  return cleanup(t.end.bind(t))
                db.close(function (err) {
                  t.notOk(err, 'no error from close()')
                  cleanup(t.end.bind(t))
                })
              }
          db.open(function (err) {
           t.notOk(err, 'no error from open()')
            db.batch(
                [
                    { type: 'put', key: 'one', value: '1' }
                  , { type: 'put', key: 'two', value: '2' }
                  , { type: 'put', key: 'three', value: '3' }
                ]
              , function (err) {
                  t.notOk(err, 'no error from batch()')
                  testFn(db, t, done, loc)
                }
            )
          })
        })
      })
    }

module.exports = {
    location       : location
  , cleanup        : cleanup
  , lastLocation   : lastLocation
  , setUp          : setUp
  , tearDown       : tearDown
  , collectEntries : collectEntries
  , makeExistingDbTest : makeExistingDbTest
}
