var levelup = require('level-test')()
var base = require('../')(levelup('test-mixed-value-encodings-per-del'))

var test = require('tape')

test('subsections support mixed encodings per del', function (t) {
  t.plan(6)

  var foo = base.sublevel('foo')
  var bar = base.sublevel('bar')

  foo.put('foo1', 'foo1-value', { valueEncoding: 'utf8' }, function () {
    bar.put('bar1', { obj: 'ect' }, { valueEncoding: 'json' }, function () {

      foo.get('foo1', { valueEncoding: 'utf8' }, function (err, value) {
        t.notOk(err, 'getting string value by key has no error')
        t.equal(value, 'foo1-value', 'and returns value for that key')

        foo.del('foo1', { valueEncoding: 'utf8' }, function (err, value) {
          foo.get('foo1', { valueEncoding: 'utf8' }, function (err, value) {
            t.equal(err.name, 'NotFoundError', 'properly deletes utf8 encoded value')
          })
        })
      })

      bar.get('bar1', { valueEncoding: 'json' }, function (err, value) {
        t.notOk(err, 'getting object value by key has no error')
        t.equal(value.obj, 'ect', 'and returns value for that key')

        bar.del('bar1', { valueEncoding: 'json' }, function (err, value) {
          bar.get('bar1', { valueEncoding: 'json' }, function (err, value) {
            t.equal(err.name, 'NotFoundError', 'properly deletes json encoded value')
          })
        })
      })

    })
  })
})
