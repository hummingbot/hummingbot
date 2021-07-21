const {isImportOrExport, EMPTY_NEWLINE} = require('@mdx-js/util')
const extractImportsAndExports = require('./extract-imports-and-exports')

module.exports = mdxjs

mdxjs.default = mdxjs

tokenizeEsSyntax.locator = tokenizeEsSyntaxLocator

function mdxjs() {
  const parser = this.Parser
  const compiler = this.Compiler

  if (parser && parser.prototype && parser.prototype.blockTokenizers) {
    attachParser(parser)
  }

  if (compiler && compiler.prototype && compiler.prototype.visitors) {
    attachCompiler(compiler)
  }
}

function attachParser(parser) {
  const blocks = parser.prototype.blockTokenizers
  const methods = parser.prototype.blockMethods

  blocks.esSyntax = tokenizeEsSyntax

  tokenizeEsSyntax.notInBlock = true

  methods.splice(methods.indexOf('paragraph'), 0, 'esSyntax')
}

function attachCompiler(compiler) {
  const proto = compiler.prototype

  proto.visitors = Object.assign({}, proto.visitors, {
    import: stringifyEsSyntax,
    export: stringifyEsSyntax
  })
}

function stringifyEsSyntax(node) {
  return node.value.trim()
}

function tokenizeEsSyntax(eat, value) {
  const index = value.indexOf(EMPTY_NEWLINE)
  const subvalue = index !== -1 ? value.slice(0, index) : value

  if (isImportOrExport(subvalue)) {
    const nodes = extractImportsAndExports(subvalue, this.file)
    nodes.map(node => eat(node.value)(node))
  }
}

function tokenizeEsSyntaxLocator(value, _fromIndex) {
  return isImportOrExport(value) ? -1 : 1
}
