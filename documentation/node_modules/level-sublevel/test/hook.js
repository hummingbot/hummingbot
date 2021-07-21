var level = require('level-test')()
var Sublevel = require('../')

function sl (name) {
  return Sublevel(level(name), {sep: '~'}) 
}

require('tape')('sublevel', function (t) {

  var base = sl('test-sublevel')

  var a    = base.sublevel('A')
  var b    = base.sublevel('SEQ')

  var i = 0

  function all(db, cb) {
    var o = {}
    db.createReadStream({end: '\xff\xff'}).on('data', function (data) {
      o[data.key.toString()] = data.value.toString()
    })
    .on('end', function () {
      cb(null, o)
    })
    .on('error', cb)
  }

  a.pre(function (ch, add) {
    console.log(ch)
    add({key: i++, value: ch.key, type: 'put'}, b)
  })

  var n = 3, _a, _b, _c

  a.put('a', _a ='AAA_'+Math.random(), next)
  a.put('b', _b = 'BBB_'+Math.random(), next)
  a.put('c', _c = 'CCC_'+Math.random(), next)

  function next () {
    if(--n) return

    all(base, function (err, obj) {
      console.log(obj)
      t.deepEqual(obj, 
        { '~A~a': _a,
          '~A~b': _b,
          '~A~c': _c,
          '~SEQ~0': 'a',
          '~SEQ~1': 'b',
          '~SEQ~2': 'c' })
      t.end()
    })
  }

})
