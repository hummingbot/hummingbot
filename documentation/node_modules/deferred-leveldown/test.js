var test              = require('tape')
  , DeferredLevelDOWN = require('./')

test('single operation', function (t) {
  var called = false
  var ld = new DeferredLevelDOWN('loc')
  ld.put('foo', 'bar', function (v) {
    called = v
  })
  t.ok(called === false, 'not called')
  ld.setDb({ put: function (key, value, options, callback) {
    t.equal(key, 'foo', 'correct key')
    t.equal(value, 'bar', 'correct value')
    t.deepEqual({}, options, 'empty options')
    callback('called')
  }})

  t.ok(called === 'called', 'function called')

  t.end()
})

test('many operations', function (t) {
  var calls = []
  var ld = new DeferredLevelDOWN('loc')
    , puts    = 0
    , gets    = 0
    , batches = 0

  ld.put('foo1', 'bar1', function (v) { calls.push({ type: 'put', key: 'foo1', v: v }) })
  ld.get('woo1', function (v) { calls.push({ type: 'get', key: 'woo1', v: v }) })
  ld.put('foo2', 'bar2', function (v) { calls.push({ type: 'put', key: 'foo2', v: v }) })
  ld.get('woo2', function (v) { calls.push({ type: 'get', key: 'woo2', v: v }) })
  ld.del('blergh', function (v) { calls.push({ type: 'del', key: 'blergh', v: v }) })
  ld.batch([
      { type: 'put', key: 'k1', value: 'v1' }
    , { type: 'put', key: 'k2', value: 'v2' }
   ], function () { calls.push({ type: 'batch', keys: 'k1,k2' }) })
  ld.batch().put('k3', 'v3').put('k4', 'v4').write(function () {
    calls.push({ type: 'batch', keys: 'k3,k4' })
  })

  t.ok(calls.length === 0, 'not called')

  ld.setDb({
      put: function (key, value, options, callback) {
        if (puts++ === 0) {
          t.equal(key, 'foo1', 'correct key')
          t.equal(value, 'bar1', 'correct value')
          t.deepEqual({}, options, 'empty options')
        } else {
          t.equal(key, 'foo2', 'correct key')
          t.equal(value, 'bar2', 'correct value')
          t.deepEqual({}, options, 'empty options')
        }
        callback('put' + puts)
      }
    , get: function (key, options, callback) {
        if (gets++ === 0) {
          t.equal('woo1', key, 'correct key')
          t.deepEqual({}, options, 'empty options')
        } else {
          t.equal('woo2', key, 'correct key')
          t.deepEqual({}, options, 'empty options')
        }
        callback('gets' + gets)
      }
    , del: function (key, options, callback) {
        t.equal('blergh', key, 'correct key')
        t.deepEqual({}, options, 'empty options')
        callback('del')
      }
    , batch: function (arr, options, callback) {
        if (batches++ === 0) {
          t.deepEqual(arr, [
              { type: 'put', key: 'k1', value: 'v1' }
            , { type: 'put', key: 'k2', value: 'v2' }
          ], 'correct batch')
        } else {
          t.deepEqual(arr, [
              { type: 'put', key: 'k3', value: 'v3' }
            , { type: 'put', key: 'k4', value: 'v4' }
          ], 'correct batch')
        }
        callback('batches' + batches)
      }
  })

  t.equal(calls.length, 7, 'all functions called')
  t.deepEqual(calls, [
      { type: 'put', key: 'foo1', v: 'put1' }
    , { type: 'get', key: 'woo1', v: 'gets1' }
    , { type: 'put', key: 'foo2', v: 'put2' }
    , { type: 'get', key: 'woo2', v: 'gets2' }
    , { type: 'del', key: 'blergh', v: 'del' }
    , { type: 'batch', keys: 'k1,k2' }
    , { type: 'batch', keys: 'k3,k4' }
  ], 'calls correctly behaved')

  t.end()
})
