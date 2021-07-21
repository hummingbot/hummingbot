var test = require('tape')
var level = require('level-test')()
var SubLevel = require('../')

test('sublevel - batch', function (t) {

  var base = SubLevel(level('test-sublevel'))

  var lc = [], uc = []

  base.post(/^[a-z]/, function (data) {
    lc.push(data.key)
  })

  base.post(/^[A-Z]/, function (data) {
   uc.push(data.key)
  })
  var n = 4

  base.put('thing',    Math.random(), next)
  base.put('Thing',    Math.random(), next)
  base.put('lalala',   Math.random(), next)
  base.put('WHATEVER', Math.random(), next)

  function next () {
    if(--n) return
    t.deepEqual(lc.sort(), ['lalala', 'thing'])
    t.deepEqual(uc.sort(), ['Thing', 'WHATEVER'])
    t.end()
  }
})


test('sublevel - post hook rang on sublevel', function (t) {

  var db = SubLevel(level('test-sublevel2'))
  var base = db.sublevel('stuff')

  var lc = [], uc = []

  base.post(/^[a-z]/, function (data) {
    console.log('POST', data)
    lc.push(data.key)
  })

  base.post(/^[A-Z]/, function (data) {
   uc.push(data.key)
  })
  var n = 4

  base.put('thing',    Math.random(), next)
  base.put('Thing',    Math.random(), next)
  base.put('lalala',   Math.random(), next)
  base.put('WHATEVER', Math.random(), next)

  function next () {
    if(--n) return
    t.deepEqual(lc.sort(), ['lalala', 'thing'])
    t.deepEqual(uc.sort(), ['Thing', 'WHATEVER'])
    t.end()
  }
})

