var test = require('tape')
var range = require('../')


function reverse(t, opts) {
  var _opts = JSON.parse(JSON.stringify(opts))
  var opts = range(opts)
  if(opts.reverse) {
    t.ok(opts.start   == _opts.end)
    t.ok(opts.end     == _opts.start)
  }
  else {
    t.ok(opts.start   == _opts.start)
    t.ok(opts.end     == _opts.end)
  }
  t.ok(opts.reverse == _opts.reverse)

}

function ordered(t, opts, reverse) {
  var opts = range(opts)
  //don't change order if there is only start OR end,
  //but not both.

  console.log([!!opts.reverse,'===', opts.start, '>', opts.end].join(' '))
  t.ok(!!opts.reverse === opts.start > opts.end, 
    [opts.start, opts.reverse ? '>' : '<', opts.end].join(' ')
  )
}


test('set correct order', function (t) {
  ordered = ordered.bind(null, t)
  ordered({start: 'a', end: 'z'})
  ordered({start: 'v', end: 'e'})
  ordered({start: 'e', end: 'v', reverse: true})
  ordered({start: 'v', end: 'e', reverse: true})
  t.end()
})

//{start: 'v'} and {end: 'v'} are both valid orders,
//from start: 'v' to the end of the db,
//and end: 'v' from the start of the db to 'v'.
//so don't fix them.

test("don't change order", function (t) {
  reverse = reverse.bind(null, t)
  reverse({start: 'v',           reverse: true})
  reverse({            end: 'v', reverse: true})
  reverse({            end: 'v'               })
  reverse({start: 'v'                         })
  t.end()
})


test('alias min and max to start and end', function (t) {

  function alias(fixable, fixed) {
    fixable = range(fixable)
    t.equal(fixable.start,   fixed.start,   'start')
    t.equal(fixable.end,     fixed.end,     'end')
    t.equal(fixable.reverse, fixed.reverse, 'reverse')
  }

  alias({min: 'a', max: 'z'}, {start: 'a', end: 'z'})
  alias({min: 'a', max: 'z', reverse: true}, {start: 'z', end: 'a', reverse: true})
  alias({max: 'z'}, {end: 'z'})
  alias({max: 'z', reverse: true}, {start: 'z', reverse: true})
  alias({min: 'a'}, {start: 'a'})
  alias({min: 'a', reverse: true}, {end: 'a', reverse: true})

  t.end()
})


test('no side effects', function (t) {
  var fixable = {min: 'a', max: 'b', reverse: true}
  range(fixable)
  t.deepEqual(fixable, {min: 'a', max: 'b', reverse: true})
  t.end()
})
