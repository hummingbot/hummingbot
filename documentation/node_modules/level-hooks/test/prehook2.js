var level = require('level-test')()

var Hooks   = require('../')

var assert  = require('assert')
var mac     = require('macgyver')().autoValidate()

var db = level('map-reduce-prehook-test')

var SEQ = 0, LOGSEQ = 0

Hooks(db)

db.hooks.pre(/^\w/, mac(function (ch, add) {
  //iterate backwards so you can push without breaking stuff.
  var key = ch.key
  add({
    type: 'put', 
    key: ++SEQ,
    value: key.toString()
  }, '~log~')

  add({
    type: 'put', key: new Buffer('~seq'),
    value: new Buffer(SEQ.toString())
  })

}).atLeast(1))

var removeLogHook = db.hooks.pre('~log', mac(function (ch, add) {
  //iterate backwards so you can push without breaking stuff.
  console.log('LOG2', ch)
  var key = ch.key
  add({
    type: 'put', 
    key: ++LOGSEQ,
    value: Date.now(),
    prefix: '~LOGSEQ~'
  })

}).atLeast(1))


var n = 4

var next = mac(function () {
  console.log('test', n)
  if(--n) return

  db.get('~seq', mac(function (err, val) {
    console.log('seq=', ''+val)
    assert.equal(Number(''+val), 4)
    db.readStream({start: '~log~', end: '~log~~'})
      .on('data', function (data) {
        console.log(data.key.toString(), data.value.toString())
      })
  }).once())

  var all = {}

  db.readStream()
    .on('data', function (data) {
      all[data.key.toString()] = data.value.toString()
    })
    .on('end', function () {
      console.log(all)

      //these will be times, and will have changed.
      delete all['~LOGSEQ~1']
      delete all['~LOGSEQ~2']
      delete all['~LOGSEQ~3']

      assert.deepEqual(all, {
        hello: 'whatever',
        hi: 'message',
        thing: 'WHATEVER',
        yoohoo: 'test 1, 2',
        '~log~1': 'hello',
        '~log~2': 'hi',
        '~log~3': 'yoohoo',
        '~log~4': 'thing',
        '~seq': '4' 
      })

    })

}).times(4)

db.put('hello' , 'whatever' , next)
db.put('hi'    , 'message'  , next)
db.put('yoohoo', 'test 1, 2', next)

removeLogHook()

db.put('thing' , 'WHATEVER' , next)

