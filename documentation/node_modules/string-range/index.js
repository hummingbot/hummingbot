
//force to a valid range
var range = exports.range = function (obj) {
  return null == obj ? {} : 'string' === typeof range ? {
      min: range, max: range + '\xff'
    } :  obj
}

//turn into a sub range.
var prefix = exports.prefix = function (range, within, term) {
  range = exports.range(range)
  var _range = {}
  term = term || '\xff'
  if(range instanceof RegExp || 'function' == typeof range) {
    _range.min = within
    _range.max   = within + term,
    _range.inner = function (k) {
      var j = k.substring(within.length)
      if(range.test)
        return range.test(j)
      return range(j)
    }
  }
  else if('object' === typeof range) {
    _range.min = within + (range.min || range.start || '')
    _range.max = within + (range.max || range.end   || (term || '~'))
    _range.reverse = !!range.reverse
  }
  return _range
}

//return a function that checks a range
var checker = exports.checker = function (range) {
  if(!range) range = {}

  if ('string' === typeof range)
    return function (key) {
      return key.indexOf(range) == 0
    }
  else if(range instanceof RegExp)
    return function (key) {
      return range.test(key)
    }
  else if('object' === typeof range)
    return function (key) {
      var min = range.min || range.start
      var max = range.max || range.end

      // fixes keys passed as ints from sublevels
      key = String(key)

      return (
        !min || key >= min
      ) && (
        !max || key <= max
      ) && (
        !range.inner || (
          range.inner.test 
            ? range.inner.test(key)
            : range.inner(key)
        )
      )
    }
  else if('function' === typeof range)
    return range
}
//check if a key is within a range.
var satifies = exports.satisfies = function (key, range) {
  return checker(range)(key)
}


