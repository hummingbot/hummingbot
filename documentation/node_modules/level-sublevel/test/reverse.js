var test = require('tape')
var level = require('level-test')()
var base = require('../')(level('test-sublevel-reverse'))

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

    function order(a, b) {
      t.deepEqual(a, b)
      t.equal(JSON.stringify(a), JSON.stringify(b))
    }

    db.batch(Object.keys(docs).map(function (key) {
      console.log(key, docs[key])
      return {key: key, value: docs[key], type: 'put'}
    }), function (err) {
      t.notOk(err) 

      all(db, {}, function (err, all) {
        order(all, docs)
      })

      all(db, {min: 'a~'}, function (err, all) {
        order(all, {
          b: 'banana',
          c: 'cherry',
          d: 'durian',
          e: 'elder-berry'
        })
      })

      all(db, {min: 'b'}, function (err, all) {
        order(all, {
          b: 'banana',
          c: 'cherry',
          d: 'durian',
          e: 'elder-berry'
        })
      })


      all(db, {min: 'a~', reverse: true}, function (err, all) {
        order(all, {
          e: 'elder-berry',
          d: 'durian',
          c: 'cherry',
          b: 'banana'
        })
      })

      all(db, {min: 'c~', reverse: true}, function (err, all) {
        console.log(all)
        order(all, {
          e: 'elder-berry',
          d: 'durian'
        })
      })

      all(db, {min: 'c~', max: 'd~'}, function (err, all) {
        console.log(all)
        order(all, {
          d: 'durian',
        })
      })

      all(db, {min: 'a~'}, function (err, all) {
        order(all, {
          b: 'banana',
          c: 'cherry',
          d: 'durian',
          e: 'elder-berry'
        })
      })

      all(db, {min: 'c~'}, function (err, all) {
        console.log('d, e', all)
        order(all, {
          d: 'durian',
          e: 'elder-berry'
        })
      })

      all(db, {min: 'c~', max: 'd~', reverse: true}, function (err, all) {
        console.log(all)
        order(all, {
          d: 'durian',
        })
      })
    })
  })
}

var A = base.sublevel('A')
makeTest(base, 'simple')

makeTest(A, 'sublevel')

makeTest(base, 'simple, again')

var A_B = A.sublevel('B')
makeTest(A_B, 'sublevel2')

makeTest(A, 'sublevel, again')

makeTest(base, 'simple, again 2')

