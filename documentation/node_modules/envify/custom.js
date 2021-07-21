var esprima = require('esprima')
  , through = require('through')

var processEnvPattern = /\bprocess\.env\b/

module.exports = function(rootEnv) {
  rootEnv = rootEnv || process.env || {}

  return function envify(file, argv) {
    if (/\.json$/.test(file)) return through()

    var Syntax = esprima.Syntax
    var buffer = []
    argv = argv || {}

    return through(write, flush)

    function write(data) {
      buffer.push(data)
    }

    function transform(source, envs) {
      var args  = [].concat(envs[0]._ || []).concat(envs[1]._ || [])
      var purge = args.indexOf('purge') !== -1
      var replacements = []

      function match(node) {
        return (
          node.type === Syntax.MemberExpression
          && node.object.type === Syntax.MemberExpression
          && node.object.computed === false
          && node.object.object.type === Syntax.Identifier
          && node.object.object.name === 'process'
          && node.object.property.type === Syntax.Identifier
          && node.object.property.name === 'env'
          && (node.computed ? node.property.type === Syntax.Literal : node.property.type === Syntax.Identifier)
        )
      }

      esprima.parse(source, { tolerant: true }, function(node, meta) {
        if (match(node)) {
          var key = node.property.name || node.property.value
          for (var i = 0; i < envs.length; i++) {
            var value = envs[i][key]
            if (value !== undefined) {
              replacements.push({ node: node, meta: meta, value: JSON.stringify(value) })
              return
            }
          }
          if (purge) {
            replacements.push({ node: node, meta: meta, value: undefined })
          }
        } else if (node.type === Syntax.AssignmentExpression) {
          for (var i = 0; i < replacements.length; ++i) {
            if (replacements[i].node === node.left) {
              replacements.splice(i, 1)
            }
          }
        }
      })

      var result = source
      if (replacements.length > 0) {
        replacements.sort(function (a, b) {
          return b.meta.start.offset - a.meta.start.offset
        })
        for (var i = 0; i < replacements.length; i++) {
          var r = replacements[i]
          result = result.slice(0, r.meta.start.offset) + r.value + result.slice(r.meta.end.offset)
        }
      }

      return result
    }

    function flush() {
      var source = buffer.join('')

      if (processEnvPattern.test(source)) {
        try {
          source = transform(source, [argv, rootEnv])
        } catch(err) {
          return this.emit('error', err)
        }
      }

      this.queue(source)
      this.queue(null)
    }
  }
}
