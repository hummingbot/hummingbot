const inlinePlugin = require('./inline')
const blockPlugin = require('./block')

module.exports = function mathPlugin (opts) {
  if (opts == null) opts = {}
  blockPlugin.call(this, opts)
  inlinePlugin.call(this, opts)
}
