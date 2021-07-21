var level = require('level-test')()
var sublevel = require('../')
var test = require('tape')

function find(ary, test) {
  for(var i = 0; i < ary.length; i++) {
    if(test(ary[i], i, ary)) return ary[i]
  }
}

test('prehook can introspect whole batch', function (t) {

  var db    = sublevel(level('introspect'))
  var logDb = db.sublevel('log')

  var didHaveLog = 0, didNotHaveLog = 0

  var prefix = logDb.prefix()

  db.pre(function (op, add, batch) {
    if(find(batch, function (_op) {
      return op.key == _op.value && _op.key.indexOf(prefix) === 0
    }))
      didHaveLog ++
    else {
      add({key: Date.now(), value: op.key, type: 'put', prefix: logDb})
      didNotHaveLog ++
    }
  })

  db.batch([
    {key: 'foo', value: new Date(), type: 'put'},
    {key: Date.now(), value: 'foo', type: 'put', prefix: logDb},
  ], function (err) {
    if(err) console.error(err.stack)
    t.notOk(err, 'save did not error')
    t.ok(didHaveLog)
    t.end()
  })

})

test('prehook can introspect whole batch - when sublevel', function (t) {

  var db    = sublevel(level('introspect2')).sublevel('main')
  var logDb = db.sublevel('log')

  var didHaveLog = 0, didNotHaveLog = 0
  var prefix = logDb.prefix()

  db.pre(function (op, add, batch) {
    if(find(batch, function (_op) {
      return op.key == _op.value && _op.key.indexOf(prefix) === 0
    }))
      didHaveLog ++
    else {
      add({key: Date.now(), value: op.key, type: 'put', prefix: logDb})
      didNotHaveLog ++
    }
  })

  db.batch([
    {key: 'foo', value: new Date(), type: 'put'},
    {key: Date.now(), value: 'foo', type: 'put', prefix: logDb},
  ], function (err) {
    if(err) console.error(err.stack)
    t.notOk(err, 'save did not error')
    t.ok(didHaveLog)
    t.end()
  })

})
