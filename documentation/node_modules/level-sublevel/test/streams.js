var level = require('level-test')()
var sublevel = require('../')

function sl (name) {
  return sublevel(level(name), {sep: '~'})
}

require('tape')('sublevel', function (t) {

  require('rimraf').sync('/tmp/test-sublevel-readstream')

  var base = sl('test-sublevel-readstream')

  var a    = base.sublevel('A')

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

  var _a, _b, _c

  var as = a.createWriteStream()
  as.write({key: 'a', value: _a ='AAA_'+Math.random()})
  as.write({key: 'b', value: _b = 'BBB_'+Math.random()})
  as.write({key: 'c', value: _c = 'CCC_'+Math.random()})
  as.end()
  as.on('close', function () {

    all(base, function (err, obj) {
      console.log(obj)
      t.deepEqual(obj, 
        { '~A~a': _a,
          '~A~b': _b,
          '~A~c': _c
        })

      all(a, function (err, obj) {
        console.log(obj)
        t.deepEqual(obj, 
          { 'a': _a,
            'b': _b,
            'c': _c
          })
        t.end()
      })
    })
  })
})
