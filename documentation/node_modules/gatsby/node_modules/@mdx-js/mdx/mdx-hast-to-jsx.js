const {transformSync} = require('@babel/core')
const uniq = require('lodash.uniq')
const {serializeTags} = require('remark-mdx/lib/serialize/mdx-element')
const serializeMdxExpression = require('remark-mdx/lib/serialize/mdx-expression')
const toH = require('hast-to-hyperscript')
const {toTemplateLiteral} = require('@mdx-js/util')
const BabelPluginApplyMdxProp = require('babel-plugin-apply-mdx-type-prop')
const BabelPluginExtractImportNames = require('babel-plugin-extract-import-names')
const BabelPluginExtractExportNames = require('babel-plugin-extract-export-names')

function toJSX(node, parentNode = {}, options = {}) {
  if (node.type === 'root') {
    return serializeRoot(node, options)
  }

  if (node.type === 'element') {
    return serializeElement(node, options, parentNode)
  }

  // Wraps text nodes inside template string, so that we don't run into escaping issues.
  if (node.type === 'text') {
    return serializeText(node, options, parentNode)
  }

  if (node.type === 'mdxBlockExpression' || node.type === 'mdxSpanExpression') {
    return serializeMdxExpression(node)
  }

  // To do: pass `parentName` in?
  if (node.type === 'mdxBlockElement' || node.type === 'mdxSpanElement') {
    return serializeComponent(node, options, parentNode)
  }

  if (node.type === 'import' || node.type === 'export') {
    return serializeEsSyntax(node)
  }
}

function compile(options = {}) {
  this.Compiler = function (tree) {
    return toJSX(tree, {}, options)
  }
}

module.exports = compile
exports = compile
exports.toJSX = toJSX
exports.default = compile

function serializeRoot(node, options) {
  const {
    // Default options
    skipExport = false,
    wrapExport
  } = options

  const groups = {import: [], export: [], rest: []}

  for (const child of node.children) {
    let kind = 'rest'

    if (child.type === 'import' || child.type === 'export') {
      kind = child.type
    }

    groups[kind].push(child)
  }

  let layout

  // Find a default export, assumes there’s zero or one.
  groups.export = groups.export.filter(child => {
    if (child.default) {
      layout = child.value
        .replace(/^export\s+default\s+/, '')
        .replace(/;\s*$/, '')
      return false
    }

    return true
  })

  const importStatements = groups.import
    .map(childNode => toJSX(childNode, node))
    .join('\n')

  const exportStatements = groups.export
    .map(childNode => toJSX(childNode, node))
    .join('\n')

  const mdxLayout = `const MDXLayout = ${layout ? layout : '"wrapper"'}`

  const doc = groups.rest
    .map(childNode => toJSX(childNode, node, options))
    .join('')
    .replace(/^\n+|\n+$/, '')

  const fn = `function MDXContent({ components, ...props }) {
return (
  <MDXLayout {...props} components={components}>
${doc}
  </MDXLayout>
)
};
MDXContent.isMDXComponent = true`

  // Check JSX nodes against imports
  const babelPluginExtractImportNamesInstance = new BabelPluginExtractImportNames()
  const babelPluginExtractExportNamesInstance = new BabelPluginExtractExportNames()
  const importsAndExports = [importStatements, exportStatements].join('\n')
  transformSync(importsAndExports, {
    configFile: false,
    babelrc: false,
    plugins: [
      require('@babel/plugin-syntax-jsx'),
      require('@babel/plugin-syntax-object-rest-spread'),
      babelPluginExtractImportNamesInstance.plugin,
      babelPluginExtractExportNamesInstance.plugin
    ]
  })
  const importNames = babelPluginExtractImportNamesInstance.state.names
  const exportNames = babelPluginExtractExportNamesInstance.state.names

  const babelPluginApplyMdxPropInstance = new BabelPluginApplyMdxProp()
  const babelPluginApplyMdxPropToExportsInstance = new BabelPluginApplyMdxProp()

  const fnPostMdxTypeProp = transformSync(fn, {
    configFile: false,
    babelrc: false,
    plugins: [
      require('@babel/plugin-syntax-jsx'),
      require('@babel/plugin-syntax-object-rest-spread'),
      babelPluginApplyMdxPropInstance.plugin
    ]
  }).code

  const exportStatementsPostMdxTypeProps = transformSync(exportStatements, {
    configFile: false,
    babelrc: false,
    plugins: [
      require('@babel/plugin-syntax-jsx'),
      require('@babel/plugin-syntax-object-rest-spread'),
      babelPluginApplyMdxPropToExportsInstance.plugin
    ]
  }).code

  const allJsxNames = [
    ...babelPluginApplyMdxPropInstance.state.names,
    ...babelPluginApplyMdxPropToExportsInstance.state.names
  ]
  const jsxNames = allJsxNames.filter(name => name !== 'MDXLayout')

  const importExportNames = importNames.concat(exportNames)
  const fakedModulesForGlobalScope =
    `const makeShortcode = name => function MDXDefaultShortcode(props) {
  console.warn("Component " + name + " was not imported, exported, or provided by MDXProvider as global scope")
  return <div {...props}/>
};
` +
    uniq(jsxNames)
      .filter(name => !importExportNames.includes(name))
      .map(name => `const ${name} = makeShortcode("${name}");`)
      .join('\n')

  const moduleBase = `${importStatements}
${exportStatementsPostMdxTypeProps}
${fakedModulesForGlobalScope}
${mdxLayout}`

  if (skipExport) {
    return `${moduleBase}
${fnPostMdxTypeProp}`
  }

  if (wrapExport) {
    return `${moduleBase}
${fnPostMdxTypeProp}
export default ${wrapExport}(MDXContent)`
  }

  return `${moduleBase}
export default ${fnPostMdxTypeProp}`
}

function serializeElement(node, options, parentNode) {
  const parentName = parentNode.tagName
  const {type, props} = toH(
    fakeReactCreateElement,
    Object.assign({}, node, {children: []}),
    {prefix: false}
  )
  const content = serializeChildren(node, options)

  delete props.key
  const data = parentName ? {...props, parentName} : props

  const spread =
    Object.keys(data).length === 0 ? null : ' {...' + JSON.stringify(data) + '}'

  return (
    '<' +
    type +
    (spread ? ' ' + spread : '') +
    (content ? '>' + content + '</' + type + '>' : '/>')
  )
}

function serializeComponent(node, options) {
  let content = serializeChildren(node, options)
  const tags = serializeTags(
    Object.assign({}, node, {children: content ? ['!'] : []})
  )

  if (node.type === 'mdxBlockElement' && content) {
    content = '\n' + content + '\n'
  }

  return tags.open + content + (tags.close || '')
}

function serializeText(node, options, parentNode) {
  const preserveNewlines = options.preserveNewlines
  // Don't wrap newlines unless specifically instructed to by the flag,
  // to avoid issues like React warnings caused by text nodes in tables.
  const shouldPreserveNewlines = preserveNewlines || parentNode.tagName === 'p'

  if (node.value === '\n' && !shouldPreserveNewlines) {
    return node.value
  }

  return toTemplateLiteral(node.value)
}

function serializeEsSyntax(node) {
  return node.value
}

function serializeChildren(node, options) {
  const children = node.children || []
  const childOptions = Object.assign({}, options, {
    // Tell all children inside <pre> tags to preserve newlines as text nodes
    preserveNewlines: options.preserveNewlines || node.tagName === 'pre'
  })

  return children
    .map(childNode => {
      return toJSX(childNode, node, childOptions)
    })
    .join('\n')
}

// We only do this for the props, so we’re ignoring children.
function fakeReactCreateElement(name, props) {
  return {
    type: name,
    props: props,
    // Needed for `toH` to think this is React.
    key: null,
    _owner: null
  }
}
