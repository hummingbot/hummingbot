
var ranges = require('../')
var test = require('tape')

function stringify (range) {
  return '<'+[
    range.start ? JSON.stringify(range.start) + ' <=' : '',
    range.start || range.end ? 'x' : '',
    range.end ? ' <=' + JSON.stringify(range.end) : '',
    range.inner ? 
      '&& ' + range.inner.toString().substring(0, 100)
    : ''
  ].filter(function (e) {return e}).join(' ')+ '>'
}

function p(t, key, range) {
  t.ok(ranges.satisfies(key, range), 
    'key:' + key + ' satisfies range:' + stringify(range))
}
function f(t, key, range) {
  t.notOk(ranges.satisfies(key, range), 
    'key:' + key + ' *must not* satisfy range:' + stringify(range))
}
test('test range', function (t) {
  p(t, 'hi', {})
  p(t, 'hi', {start: '!', end: '~'})
  p(t, 'hi', /^\w/)
  p(t, '---hi', {start: '!', end: '~'})
  p(t, 'a---hi', {start: 'A', end: 'z'})
  f(t, '---hi', {start: 'A', end: 'z'})
  p(t, 'hi', {start: 'a', end: 'z'})
  p(t, 'words~hi', ranges.prefix({start: 'a', end: 'z'}, 'words~'))
  p(t, 'WORDS~hi', ranges.prefix(/^[a-z]/, 'WORDS~'))  

  f(t, 'WORDS~X', ranges.prefix(/^[a-z]/, 'WORDS~'))

  f(t, 'word~hi', ranges.prefix({start: 'a', end: 'z'}, 'words~'))  
  t.end()
})

test('test range min,max', function (t) {

  p(t, 'hi',     {min: '!', max: '~'})
  p(t, '---hi',  {min: '!', max: '~'})
  p(t, 'a---hi', {min: 'A', max: 'z'})
  f(t, '---hi',  {min: 'A', max: 'z'})
  p(t, 'hi',     {min: 'a', max: 'z'})
  p(t, 'words~hi',
    ranges.prefix({min: 'a', max: 'z'}, 'words~'))

  f(t, 'word~hi',
    ranges.prefix({min: 'a', max: 'z'}, 'words~'))  

  t.end()
})


test('test range2', function (t) {
  p(t, 'hi', /^\w/)
  p(t, 'hi', function (e) { return e[0] === 'h' })
  p(t, 'words~hi', ranges.prefix(/^\w/, 'words~'))
  f(t, 'word~hi', ranges.prefix(/^\w/, 'words~'))  
  t.end()
})


test("test int key within range",function(t){
  p(t,2,{start: '1', end: '3'})
  t.end();
})

test("test int key within int range",function(t){
  p(t,2,{start: 1, end: 3})
  t.end();
})
