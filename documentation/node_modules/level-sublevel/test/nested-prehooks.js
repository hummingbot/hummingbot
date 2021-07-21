var level = require('level-test')()
var Sublevel = require('../')

function sl (name) {
  return  Sublevel(level(name), { sep: '~' })

}

require('tape')('sublevel', function (t) {

  var base = sl('test-sublevel')

  var a   = base.sublevel('A')
  var a_a = a.sublevel('A')

  var as = {}
  var aas = {}

  a.pre(function (e) {
    as[e.key] = e.value
    console.log('A   :', e)
  })

  a_a.pre(function (e) {
    aas[e.key] = e.value
    console.log('A_A :', e)
  })

  var n = 3
  a.put('apple', '1', next)
  a.put('banana', '2', next)

  a_a.put('aardvark', 'animal1', next)

  function next() {
    if(--n) return
    t.deepEqual(as, {apple: '1', banana: '2'})
    t.deepEqual(aas, {aardvark: 'animal1'})
    t.end()
  }

  function all(db, cb) {
    var o = {}
    db.createReadStream().on('data', function (data) {
      o[data.key.toString()] = data.value.toString()
    })
    .on('end', function () {
      cb(null, o)
    })
    .on('error', cb)
  }
})
