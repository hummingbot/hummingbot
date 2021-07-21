var loaderUtils = require('loader-utils')
var YAML = require('yaml')

module.exports = function yamlLoader(src) {
  const { asStream, namespace, ...options } = Object.assign(
    { prettyErrors: true },
    loaderUtils.getOptions(this)
  )

  if (asStream) {
    const stream = YAML.parseAllDocuments(src, options)
    const res = []
    for (const doc of stream) {
      for (const warn of doc.warnings) this.emitWarning(warn)
      for (const err of doc.errors) throw err
      res.push(doc.toJSON())
    }
    return JSON.stringify(res)
  }

  let res = YAML.parse(src, options)
  if (namespace) {
    res = namespace.split('.').reduce(function(acc, name) {
      return acc[name]
    }, res)
  }
  return JSON.stringify(res)
}
