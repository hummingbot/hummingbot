module.exports = (babel, options) => {
  return {
    name: "default-import-converter",
    visitor: {
      ImportDeclaration(path) {
        var spec = path.node.specifiers.map(
          spec =>
            options.keys.includes(spec.local.name)
              ? babel.types.ImportDefaultSpecifier(spec.local)
              : spec
        );
        path.node.specifiers = spec;
      }
    }
  };
};
