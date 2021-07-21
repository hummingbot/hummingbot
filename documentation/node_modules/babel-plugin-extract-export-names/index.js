const {declare} = require('@babel/helper-plugin-utils')

class BabelPluginExtractExportNames {
  constructor() {
    const names = []
    this.state = {names}

    this.plugin = declare(api => {
      api.assertVersion(7)
      const {types: t} = api

      const handleDeclarations = node => {
        if (!node.declaration) {
          return
        }

        const {declarations} = node.declaration
        if (!declarations) {
          return
        }

        declarations.forEach(declaration => {
          if (t.isIdentifier(declaration.id)) {
            // Export const foo = 'bar'
            names.push(declaration.id.name)
          } else if (t.isArrayPattern(declaration.id)) {
            // Export const [ a, b ] = []
            declaration.id.elements.forEach(decl => {
              names.push(decl.name)
            })
          } else if (t.isObjectPattern(declaration.id)) {
            // Export const { a, b } = {}
            declaration.id.properties.forEach(decl => {
              names.push(decl.key.name)
            })
          }
        })
      }

      const handleSpecifiers = node => {
        const {specifiers} = node

        if (!specifiers) {
          return
        }

        specifiers.forEach(specifier => {
          if (t.isExportDefaultSpecifier(specifier)) {
            names.push(specifier.exported.name)
          } else {
            names.push(specifier.local.name)
          }
        })
      }

      return {
        visitor: {
          ExportNamedDeclaration(path) {
            handleDeclarations(path.node)
            handleSpecifiers(path.node)
          }
        }
      }
    })
  }
}

module.exports = BabelPluginExtractExportNames
