module.exports = buffer

var compiler = require('./compile/html')
var parser = require('./parse')
var preprocessor = require('./preprocess')
var postprocess = require('./postprocess')

function buffer(value, encoding, options) {
  if (typeof encoding !== 'string') {
    options = encoding
    encoding = undefined
  }

  return compiler(options)(
    postprocess(
      parser(options).document().write(preprocessor()(value, encoding, true))
    )
  )
}
