var level = require('level-test')()

var Hooks   = require('../')

var assert  = require('assert')
var mac     = require('macgyver')().autoValidate()

var db = level('map-reduce-prehook-test')

Hooks(db)

db.hooks.pre({min: 'a', max:'z'}, function (ch, add) {
  console.log(ch)
  add(ch) //this should cause an error
})

db.put('c', 'whatever', mac(function (err) {
  
  console.log('expect error:', err)
  assert.ok(err)
}).once())


