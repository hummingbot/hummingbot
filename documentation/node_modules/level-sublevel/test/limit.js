var test = require('tape')

function all (db, range, cb) {
  var o = {}
  db.createReadStream(range)
    .on('data', function (data) {
      o[data.key] = data.value
    })
    .on('end', function () {
      cb(null, o)
    })
}

function makeTest(db, name) {

  test(name, function (t) {

    t.plan(19)

    var docs = {
      a: 'apple',
      b: 'banana',
      c: 'cherry',
      d: 'durian',
      e: 'elder-berry'
    }

    function limit(a, b) {
      t.deepEqual(a, b)
      t.equal(JSON.stringify(a), JSON.stringify(b))
    }

    db.batch(Object.keys(docs).map(function (key) {
      console.log(key, docs[key])
      return {key: key, value: docs[key], type: 'put'}
    }), function (err) {
      t.notOk(err) 

      all(db, {limit: -1}, function (err, all) {
        limit(all, docs)
      })

      all(db, {limit: 2, min: 'a~'}, function (err, all) {
        limit(all, {
          b: 'banana',
          c: 'cherry'
        })
      })

      all(db, {limit: 3, min: 'b'}, function (err, all) {
        limit(all, {
          b: 'banana',
          c: 'cherry',
          d: 'durian'
        })
      })


      all(db, {limit: 2, min: 'a~', reverse: true}, function (err, all) {
        limit(all, {
          e: 'elder-berry',
          d: 'durian'
        })
      })

      all(db, {limit: 1, min: 'c~', reverse: true}, function (err, all) {
        console.log(all)
        limit(all, {
          e: 'elder-berry'
        })
      })

      all(db, {limit: 1, min: 'c~', max: 'd~'}, function (err, all) {
        console.log(all)
        limit(all, {
          d: 'durian',
        })
      })

      all(db, {limit: 3, min: 'a~'}, function (err, all) {
        limit(all, {
          b: 'banana',
          c: 'cherry',
          d: 'durian'
        })
      })

      all(db, {limit: 1, min: 'c~'}, function (err, all) {
        console.log('d, e', all)
        limit(all, {
          d: 'durian'
        })
      })

      all(db, {limit: 2, min: 'c~', max: 'd~', reverse: true}, function (err, all) {
        console.log(all)
        limit(all, {
          d: 'durian',
        })
      })
    })
  })
}


var levelup = require('level-test')()

var base = require('../')(levelup('test-sublevel-limit'))

var A = base.sublevel('A')
makeTest(base, 'simple')

makeTest(A, 'sublevel')

makeTest(base, 'simple, again')

var A_B = A.sublevel('B')
makeTest(A_B, 'sublevel2')

makeTest(A, 'sublevel, again')

makeTest(base, 'simple, again 2')

