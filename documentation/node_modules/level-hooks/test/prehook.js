var level = require('level-test')()

var Hooks   = require('../')

var assert  = require('assert')
var mac     = require('macgyver')().autoValidate()

var db = level('map-reduce-prehook-test')

var SEQ = 0

Hooks(db)

db.hooks.pre(/^\w/, mac(function (ch, add, batch) {
  //iterate backwards so you can push without breaking stuff.

  assert.ok(Array.isArray(batch))
  assert.notEqual(batch.indexOf(ch), -1)
  var key = ch.key
  add({
    type: 'put', 
    key: new Buffer('~log~'+ ++SEQ),
    value: new Buffer(JSON.stringify({
      type: ch.type, 
      key: key.toString(), 
      time: Date.now()
    }))
  })
  add({type: 'put', key: new Buffer('~seq'), value: new Buffer(SEQ.toString())})

}).atLeast(1))

var n = 3

var next = mac(function () {
  console.log('test', n)
  if(--n) return

  db.get('~seq', mac(function (err, val) {
    console.log('seq=', ''+val)
    assert.equal(Number(''+val), 3)
    db.createReadStream({start: '~log~', end: '~log~~'})
      .on('data', function (data) {
        console.log(data.key.toString(), data.value.toString())
      })
  }).once())
}).times(3)

db.put('hello' , 'whatever' , next)
db.put('hi'    , 'message'  , next)
db.put('yoohoo', 'test 1, 2', next)

