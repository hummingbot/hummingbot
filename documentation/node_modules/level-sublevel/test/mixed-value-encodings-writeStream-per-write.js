var levelup = require('level-test')()
var base = require('../')(levelup('test-mixed-value-encodings-writeStream-write'))

var test = require('tape')

test('subsections support mixed encodings per write for write stream', function (t) {
  t.plan(6)

  var foo = base.sublevel('foo')
  var foos = foo.createWriteStream()

  foos.write({ key: 'foo1', value: 'foo1-value' }, { valueEncoding: 'utf8' })
  foos.end()
  foos.on('close', function (err) {
    t.notOk(err, 'writing utf8 encoded stream has no error')

    foo.get('foo1', { valueEncoding: 'utf8' }, function (err, value) {
      t.notOk(err, 'getting string value by key has no error')
      t.equal(value, 'foo1-value', 'and returns value for that key')
    })
  })

  var bar = base.sublevel('bar')
  var bars = bar.createWriteStream()

  bars.write({ key: 'bar1', value: { obj: 'ect' }, valueEncoding: 'json' })
  bars.end()
  bars.on('close', function (err) {
    t.notOk(err, 'writing utf8 encoded stream has no error')

    bar.get('bar1', { valueEncoding: 'json' }, function (err, value) {
      t.notOk(err, 'getting object value by key has no error')
      t.equal(value.obj, 'ect', 'and returns value for that key')
    })
  })
})
