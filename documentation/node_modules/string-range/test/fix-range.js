
var fix   = require('level-fix-range')
var range = require('../')

var r = range.range(fix({min: 'a', max: 'z', reverse: true}))

console.log(r)

var _r = fix(range.prefix(r, '~thing~'))

console.log(_r)
