var tape = require('tape')
var octal = require('./')

tape('parses', function (t) {
  t.same(octal(0), 0, 'octal(0)')
  t.same(octal(10), 8, 'octal(10)')
  t.same(octal(100), 8 * 8, 'octal(100)')
  t.same(octal(8).toString(), 'NaN', 'octal(8)')
  t.end()
})
