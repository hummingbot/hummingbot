var test = require('tape')
var SubLevel = require('../')
var levelup = require('level-test')()

var base = SubLevel(levelup('test-sublevel'))

var sub = base.sublevel('fruit')

var docs = {
  '001': 'apple',
  '002': 'orange',
  '003': 'banana'
};

test('sublevel - key/value options', function (t) {

  sub.batch(Object.keys(docs).map(function (key) {
    return {key: key, value: docs[key], type: 'put'}
  }), function (err) {
    if (err) throw err

    t.plan(4)

    ;(function testCreateKeyStream () {
      var results = []
      sub.createKeyStream()
        .on('data', function (data) {
          results.push(data)
        })
        .on('end', function () {
          t.deepEqual(results, ['001', '002', '003'])
        })
    })()

    ;(function testCreateKeyReadStream () {
      var results = []
      sub.createReadStream({values: false})
        .on('data', function (data) {
          results.push(data)
        })
        .on('end', function () {
          t.deepEqual(results, ['001', '002', '003'])
        })
    })()

    ;(function testCreateValueStream () {
      var results = []
      sub.createValueStream({keys: false})
        .on('data', function (data) {
          results.push(data)
        })
        .on('end', function () {
          t.deepEqual(results, ['apple', 'orange', 'banana'])
        })
    })()

    ;(function testCreateValueReadStream () {
      var results = []
      sub.createReadStream({keys: false})
        .on('data', function (data) {
          results.push(data)
        })
        .on('end', function () {
          t.deepEqual(results, ['apple', 'orange', 'banana'])
        })
    })()
  })
})

