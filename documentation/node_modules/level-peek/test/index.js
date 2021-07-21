

var test = require('tape')
var peek  = require('../')

var levelup = require('levelup')

var db = levelup('/tmp/test-level-peek')

db.batch([
  {key: 'A', value: 'apple', type: 'put'},
  {key: 'B', value: 'banana', type: 'put'},
  {key: 'C', value: 'cherry', type: 'put'},
  {key: 'D', value: 'durian', type: 'put'},
  {key: 'E', value: 'elder-berry', type: 'put'},
], function (err) {
  if(err) throw err


  test('peek.first', function (t) {
    var n = 7

    peek.first(db, {}, function (err, key, value) {
      t.equal(value, 'apple')
      t.end()
    })

  })

  test('peek.last', function (t) {

    peek.last(db, {}, function (err, key, value) {
      t.equal(value, 'elder-berry')
      t.end()
    })

  })

  test('peek.last({end: "C"})', function (t) {

    peek.last(db, {end: 'C'}, function (err, key, value) {
      console.log('LAST')
      t.equal(value, 'cherry')
      t.end()
    })

  })

  test('peek.last({end: "D~"})', function (t) {

    peek.last(db, {end: 'D~'}, function (err, key, value) {
      console.log('LAST')
      t.equal(value, 'durian')
      t.end()
    })
  })

  //start: from a middle record
  test('peek.first({start: "C"})', function (t) {

    peek.first(db, {start: 'C'}, function (err, key, value) {
      t.equal(value, 'cherry')
      t.end()
    })

  })

  //start to after the last record.
  test('peek.last({end: "E~"})', function (t) {

    peek.last(db, {end: 'E~'}, function (err, key, value) {
      t.equal(value, 'elder-berry')
      t.end()
    })

  })

  test("peek.last({start: 'E~', end: 'E!'})", function (t) {
    peek.last(db, {start: 'E~', end: 'E!'}, function (err, key, value) {
      t.equal(value, null)
      t.end()
    })
  })
})


