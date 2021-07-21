var level  = require('level-test')()
var hooks  = require('..')

var assert = require('assert')
var mac    = require('macgyver')().autoValidate()

var db = level('map-reduce-intercept-test')
  
hooks(db)
var _batch = []
//hook keys that start with a word character
db.hooks.pre(/^\w/, mac(function (ch, add) {
  
  _batch.push(ch)
  var a
  add(a = {key: '~h', value: 'hello', type: 'put'})
  _batch.push(a)
}).atLeast(1))

//assert that it really became a batch
db.on('batch', mac(function (batch) {
  console.log('batch', _batch)
  assert.deepEqual(_batch, batch.map(function (e) {
    return {key: ''+e.key, value: ''+ e.value, type: e.type}
  }))
}).once())


db.put('hello' , 'whatever' , mac(function (){

}).once())


