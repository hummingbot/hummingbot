var test = require('tape')
var SubLevel = require('../')
var levelup = require('level-test')()
var through = require('through')

var base = SubLevel(levelup('test-sublevel'))

var sub = base.sublevel('levelup-users')


function put (user, contrib) {
  return { key: user, value: { contrib: contrib }, type: 'put', valueEncoding :  'json' };
}

var batch = [ 
  [ 'rvagg', 'leveldown' ]
, [ 'dominictarr', 'levelup' ]
, [ 'juliangruber', 'multilevel' ]
].map(function (x) { return put(x[0], x[1]) })

// the two following tests ensure that https://github.com/dominictarr/level-sublevel/issues/30 is and stays fixed
test('key only stream keys do not include sublevel prefix', function (t) {

  sub.batch(batch, function (err, res) {
    if (err) return t.fail(err)
  })

  var arr = []
  sub.createReadStream({ keys: true, values: false })
    .pipe(through(arr.push.bind(arr), function () {
      t.ok(~arr.indexOf('rvagg'), 'has rvagg without prefix')
      t.ok(~arr.indexOf('dominictarr'), 'has dominictarr without prefix')
      t.ok(~arr.indexOf('juliangruber'), 'has juliangruber without prefix')
      t.end()
    }))
})

test('key/value stream keys don not include sublevel prefix', function (t) {

  sub.batch(batch, function (err, res) {
    if (err) return t.fail(err)
  })

  var arr = []
  sub.createReadStream({ keys: true, values: true })
    .pipe(through(arr.push.bind(arr), function () {
      var keys = arr.map(function (x) { return x.key })
      t.ok(~keys.indexOf('rvagg'), 'has rvagg without prefix')
      t.ok(~keys.indexOf('dominictarr'), 'has dominictarr without prefix')
      t.ok(~keys.indexOf('juliangruber'), 'has juliangruber without prefix')
      t.end()
    }))
})
