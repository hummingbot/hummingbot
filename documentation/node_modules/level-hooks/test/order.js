
var assert = require('assert')
var alphabet = '$&[{}(=*)+]!#%7531902468`"\'?^/@\|-_abcdefghijklmnopqrstuvwxyz,.:;<>\\~'
console.log(alphabet.split('').sort().join(''))
function randomLetter(n) {
  var a = alphabet[~~(Math.random()*26)]
  return (n ? a + randomLetter(n - 1) : a).toUpperCase()
}

var sep = ','

function toKey(g) {
  return g.map(function (e) {
    return encodeURIComponent(e)
  }).join(sep)
}

function fromKey (a) {
  return a.split(sep).map(decodeURIComponent)
}

var groups = []

function gen (a) {
  var l = 3
  a = a || []
  if(a.length > 3) return

  while(l --) {
    var _a = a.slice()
    _a.push(randomLetter(3))
    gen(_a)
    _a.unshift(_a.length)
    groups.push(toKey(_a))
  }
}

gen()

