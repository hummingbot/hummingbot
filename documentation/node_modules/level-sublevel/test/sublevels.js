var levelup = require('level-test')()

var base = require('../')(levelup('test-sublevels'))

var test = require('tape')

test('subsections', function (t) {
  t.deepEqual(base.sublevels, {})

  var foo = base.sublevel('foo')
  var bar = base.sublevel('bar')

  t.deepEqual(base.sublevels, {foo: foo, bar: bar})
  t.deepEqual(foo.sublevels, {})

  t.strictEqual(base.sublevel('foo'), foo)
  t.strictEqual(base.sublevel('bar'), bar)

  console.log('prefix:', foo.prefix())
  console.log('prefix:', bar.prefix())

  var fooBlerg = foo.sublevel('blerg')
  t.deepEqual(foo.sublevels, {blerg: fooBlerg})

  t.strictEqual(foo.sublevel('blerg'), fooBlerg)

  t.end()
})





