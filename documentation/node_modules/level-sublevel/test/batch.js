var test = require('tape')
var level = require('level-test')()

function all (db, cb) {
  var obj = {}, fin = false

  function done (err) {
    if(fin) return
    fin = true
    cb(err, obj)
  }

  db.createReadStream({end: '\xff\xff'})
    .on('data', function (ch) {
      obj[ch.key] = ch.value
    })
    .on('end', done)
    .on('error', done)
}

var sublevel = require('../')
function sl(name) {
  return sublevel(level(name), {sep: "~"})
}


test('sublevel - batch', function (t) {

  var base = sl('test-sublevel')

  var a    = base.sublevel('A')
  var b    = base.sublevel('B')


  var sum  = 0

  a.batch([
    {key: 'a', value: 1, type: 'put'},
    {key: 'b', value: 2, type: 'put'},
    {key: 'c', value: 3, type: 'put'},
    {key: 'd', value: 4, type: 'put'},
    {key: 'e', value: 5, type: 'put'},
  ], function (err) {
    all(a, function (err, obj) {
      t.notOk(err)
      var keys = Object.keys(obj).join('')
      for(var k in obj) {
        sum += Number(obj[k])
      }
      t.equal(keys, 'abcde')
      t.equal(sum, 15)
      t.end()
    })
  })

})

test('sublevel - prefixed batches', function (t) {

  var base = sl('test-sublevel2')

  var a    = base.sublevel('A')
  var b    = base.sublevel('B')

  base.batch([
    {key: 'a', value: 1, type: 'put'},
    {key: 'b', value: 2, type: 'put', prefix: b},
    {key: 'c', value: 3, type: 'put'},
    {key: 'd', value: 4, type: 'put', prefix: a},
    {key: 'e', value: 5, type: 'put', prefix: base},
  ], function (err) {
    all(base, function (_, obj) {
      t.deepEqual(obj, {
        'a': '1',
        'c': '3',
        'e': '5',
        '~A~d': '4',
        '~B~b': '2'
      })
      console.log(obj)
      t.end()
    })
  })
})

test('sublevel - prefixed batches on subsection', function (t) {

  var base = sl('test-sublevel3')

  var a    = base.sublevel('A')
  var b    = base.sublevel('B')

  a.batch([
    {key: 'a', value: 1, type: 'put', prefix: base},
    {key: 'b', value: 2, type: 'put', prefix: b},
    {key: 'c', value: 3, type: 'put', prefix: base},
    {key: 'd', value: 4, type: 'put'},
    {key: 'e', value: 5, type: 'put', prefix: base},
  ], function (err) {
    all(base, function (_, obj) {
      t.deepEqual(obj, {
        'a': '1',
        'c': '3',
        'e': '5',
        '~A~d': '4',
        '~B~b': '2'
      })
      t.end()
    })
  })
})


test('sublevel - prefixed batches on subsection - strings', function (t) {

  var base = sl('test-sublevel4')

  var a    = base.sublevel('A')
  var b    = base.sublevel('B')
  var b_c    = b.sublevel('C')

  base.batch([
    {key: 'a', value: 1, type: 'put'},
    {key: 'b', value: 2, type: 'put', prefix: b.prefix()},
    {key: 'c', value: 3, type: 'put'},
    {key: 'd', value: 4, type: 'put', prefix: a.prefix()},
    {key: 'e', value: 5, type: 'put'},
    {key: 'f', value: 6, type: 'put', prefix: b_c.prefix()},
  ], function (err) {
    all(base, function (_, obj) {
      t.deepEqual(obj, {
        'a': '1',
        'c': '3',
        'e': '5',
        '~A~d': '4',
        '~B~b': '2',
        '~B~~C~f': '6'
      })
      console.log(obj)
      t.end()
    })
  })
})

test('sublevel - batch - chained', function (t) {

  var base = sl('test-sublevel5')

  var a    = base.sublevel('A')
  var b    = base.sublevel('B')


  var sum  = 0

  a.batch()
    .put('a', 1)
    .put('b', 2)
    .put('c', 3)
    .put('d', 4)
    .put('e', 5)
  .write(function (err) {
    all(a, function (err, obj) {
      t.notOk(err)
      var keys = Object.keys(obj).join('')
      for(var k in obj) {
        sum += Number(obj[k])
      }
      t.equal(keys, 'abcde')
      t.equal(sum, 15)
      t.end()
    })
  })

})

test('sublevel - prefixed batches - chained', function (t) {

  var base = sl('test-sublevel6')

  var a    = base.sublevel('A')
  var b    = base.sublevel('B')

  base.batch()
    .put('a', 1)
    .put('b', 2, {prefix: b})
    .put('c', 3)
    .put('d', 4, {prefix: a})
    .put('e', 5, {prefix: base})
  .write(function (err) {
    all(base, function (_, obj) {
      t.deepEqual(obj, {
        'a': '1',
        'c': '3',
        'e': '5',
        '~A~d': '4',
        '~B~b': '2'
      })
      console.log(obj)
      t.end()
    })
  })
})

test('sublevel - prefixed batches on subsection - chained', function (t) {

  var base = sl('test-sublevel7')

  var a    = base.sublevel('A')
  var b    = base.sublevel('B')

  a.batch()
    .put('a', 1, {prefix: base})
    .put('b', 2, {prefix: b})
    .put('c', 3, {prefix: base})
    .put('d', 4)
    .put('e', 5, {prefix: base})
  .write(function (err) {
    all(base, function (_, obj) {
      t.deepEqual(obj, {
        'a': '1',
        'c': '3',
        'e': '5',
        '~A~d': '4',
        '~B~b': '2'
      })
      t.end()
    })
  })
})


test('sublevel - prefixed batches on subsection - strings - chained', function (t) {

  var base = sl('test-sublevel8')

  var a    = base.sublevel('A')
  var b    = base.sublevel('B')
  var b_c    = b.sublevel('C')

  base.batch()
    .put('a', 1)
    .put('b', 2, {prefix: b.prefix()})
    .put('c', 3)
    .put('d', 4, {prefix: a.prefix()})
    .put('e', 5)
    .put('f', 6, {prefix: b_c.prefix()})
  .write(function (err) {
    all(base, function (_, obj) {
      t.deepEqual(obj, {
        'a': '1',
        'c': '3',
        'e': '5',
        '~A~d': '4',
        '~B~b': '2',
        '~B~~C~f': '6'
      })
      console.log(obj)
      t.end()
    })
  })
})

test('sublevel - delete - chained', function(t) {
  var base = sl('test-sublevel9')

  var a    = base.sublevel('A')
  var b    = base.sublevel('B')

  var sum  = 0

  a.batch()
    .put('a', 1)
    .put('b', 2)
    .put('c', 3)
    .put('d', 4)
    .put('e', 5)
  .write()

  a.batch()
    .del('c')
    .del('e')
  .write(function (err) {
    all(a, function (err, obj) {
      t.notOk(err)
      var keys = Object.keys(obj).join('')
      for(var k in obj) {
        sum += Number(obj[k])
      }
      t.equal(keys, 'abd')
      t.equal(sum, 7)
      t.end()
    })
  })
})
