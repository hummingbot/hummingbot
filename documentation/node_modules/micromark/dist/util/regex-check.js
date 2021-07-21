module.exports = regexCheck

var fromCharCode = require('../constant/from-char-code')

function regexCheck(regex) {
  return check
  function check(code) {
    return regex.test(fromCharCode(code))
  }
}
