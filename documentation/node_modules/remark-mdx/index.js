'use strict'

var parse = require('./lib/parse')
var serialize = require('./lib/serialize')

module.exports = mdx

// I think this is needed for webpack? 😔
mdx.default = mdx

function mdx() {
  var parser = this.Parser
  var compiler = this.Compiler

  if (isRemarkParser(parser)) {
    parse(parser)
  }

  if (isRemarkCompiler(compiler)) {
    serialize(compiler)
  }
}

function isRemarkParser(parser) {
  return Boolean(parser && parser.prototype && parser.prototype.blockTokenizers)
}

function isRemarkCompiler(compiler) {
  return Boolean(compiler && compiler.prototype && compiler.prototype.visitors)
}
