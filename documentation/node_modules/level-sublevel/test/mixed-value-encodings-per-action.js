var levelup = require('level-test')()
var base = require('../')(levelup('test-mixed-value-encodings-per-put'))

var test = require('tape')

test('subsections support mixed encodings per put', function (t) {
  t.plan(10)

  var foo = base.sublevel('foo')
  var bar = base.sublevel('bar')

  foo.put('foo1', 'foo1-value', { valueEncoding: 'utf8' }, function () {
    bar.put('bar1', { obj: 'ect' }, { valueEncoding: 'json' }, function () {

      foo.get('foo1', { valueEncoding: 'utf8' }, function (err, value) {
        t.notOk(err, 'getting string value by key has no error')
        t.equal(value, 'foo1-value', 'and returns value for that key')
      })

      bar.get('bar1', { valueEncoding: 'json' }, function (err, value) {
        t.notOk(err, 'getting object value by key has no error')
        t.equal(value.obj, 'ect', 'and returns value for that key')
      })

      var foodata, fooerr

      foo.createReadStream({ start: 'foo1', end: 'foo1\xff', valueEncoding: 'utf8' })
        .on('data', function (d) { foodata = d })
        .on('error', function (err) { fooerr = err })
        .on('end', function () {
          t.notOk(fooerr, 'streaming string value by key emits no error')  
          t.equal(foodata.key, 'foo1', 'streaming string value emits key')  
          t.equal(foodata.value, 'foo1-value', 'streaming string value emits value')  
        })

      var bardata, barerr

      bar.createReadStream({ start: 'bar1', end: 'bar1\xff', valueEncoding: 'json' })
        .on('data', function (d) { bardata = d })
        .on('error', function (err) { barerr = err })
        .on('end', function () {
          t.notOk(barerr, 'streaming object value by key emits no error')  
          t.equal(bardata.key, 'bar1', 'streaming string value emits key')  
          t.equal(bardata.value.obj, 'ect', 'streaming object value emits value')  
        })
    })
  })

})
