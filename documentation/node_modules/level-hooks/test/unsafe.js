var level = require('level-test')()

var Hooks   = require('../')

var assert  = require('assert')
var mac     = require('macgyver')().autoValidate()

var db = level('map-reduce-prehook-test')

Hooks(db)

//safe: false means do not prevent me from inserting into the same range.
//when this option is set, the user's hook is responsible for not
//causing a stack overflow.
db.hooks.pre({min: 'a', max:'z', safe: false}, function (ch, add) {
  console.log(ch)
  //this is an absurd example
  if(ch.key !== 'p')
    add({key: 'p', value: ch.key, type: 'put'}) //this should cause an error
})

db.put('c', 'whatever', mac(function (err) {
  assert.ifError(err)
  db.get('p', mac(function (err, c) {
    assert.ifError(err)
    assert.equal(c, 'c')
  }).once())
}).once())


