var unicodePunctuation = require('../constant/unicode-punctuation-regex')
var check = require('../util/regex-check')

// Size note: removing ASCII from the regex and using `ascii-punctuation` here
// In fact adds to the bundle size.
module.exports = check(unicodePunctuation)
