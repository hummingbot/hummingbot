import {
  attachScopes
} from 'rollup-pluginutils';
import {
  walk
} from 'estree-walker';
import {
  parse
} from 'acorn';
import makeLegalIdentifier from './makeLegalIdentifier';
import MagicString from 'magic-string';

function isReference(node, parent) {
  if (node.type === 'MemberExpression') {
    return !node.computed && isReference(node.object, node);
  }

  if (node.type === 'Identifier') {
    // TODO is this right?
    if (parent.type === 'MemberExpression') return parent.computed || node === parent.object;

    // disregard the `bar` in { bar: foo }
    if (parent.type === 'Property' && node !== parent.value) return false;

    // disregard the `bar` in `class Foo { bar () {...} }`
    if (parent.type === 'MethodDefinition') return false;

    // disregard the `bar` in `export { foo as bar }`
    if (parent.type === 'ExportSpecifier' && node !== parent.local) return;

    return true;
  }
}

function flatten(node) {
  let name;
  let parts = [];

  while (node.type === 'MemberExpression') {
    parts.unshift(node.property.name);
    node = node.object;
  }

  name = node.name;
  parts.unshift(name);

  return {
    name,
    keypath: parts.join('.')
  };
}


export default function(code, id, mod1, mod2, sourceMap) {
  let ast;

  try {
    ast = parse(code, {
      ecmaVersion: 9,
      sourceType: 'module'
    });
  } catch (err) {
    err.message += ` in ${id}`;
    throw err;
  }
  // analyse scopes
  let scope = attachScopes(ast, 'scope');

  let imports = {};
  ast.body.forEach(node => {
    if (node.type === 'ImportDeclaration') {
      node.specifiers.forEach(specifier => {
        imports[specifier.local.name] = true;
      });
    }
  });

  const magicString = new MagicString(code);

  let newImports = {};

  function handleReference(node, name, keypath, parent) {
    if ((mod1.has(keypath) || mod2.has(keypath)) && !scope.contains(name) && !imports[name]) {
      if (mod2.has(keypath) && parent.__handled) {
        return;
      }
      let module = mod1.has(keypath) ? mod1.get(keypath) : mod2.get(keypath);
      let moduleName, hash;
      if (typeof module === 'string') {
        moduleName = module;
        hash = `${keypath}:${moduleName}:default`;
      } else {
        moduleName = module[0];
        hash = `${keypath}:${moduleName}:${module[1]}`;
      }
      // prevent module from importing itself
      if (moduleName === id) return;

      const importLocalName = name === keypath ? name : makeLegalIdentifier(`$inject_${keypath}`);

      if (!newImports[hash]) {
        newImports[hash] = `import ${typeof module === 'string' ? importLocalName : `{ ${module[1]} as ${importLocalName} }`} from ${JSON.stringify(moduleName)};`;
      }

      if (name !== keypath) {
        magicString.overwrite(node.start, node.end, importLocalName, {storeName: true});
      }
      if (mod1.has(keypath)) {
        node.__handled = true;
      }
    }
  }

  walk(ast, {
    enter(node, parent) {
      if (sourceMap) {
        magicString.addSourcemapLocation(node.start);
        magicString.addSourcemapLocation(node.end);
      }

      if (node.scope) scope = node.scope;

      // special case – shorthand properties. because node.key === node.value,
      // we can't differentiate once we've descended into the node
      if (node.type === 'Property' && node.shorthand) {
        const name = node.key.name;
        handleReference(node, name, name);
        return this.skip();
      }

      if (isReference(node, parent)) {
        const {
          name,
          keypath
        } = flatten(node);
        handleReference(node, name, keypath, parent);
      }
    },
    leave(node) {
      if (node.scope) scope = scope.parent;
    }
  });

  const keys = Object.keys(newImports);
  if (!keys.length) return null;

  const importBlock = keys.map(hash => newImports[hash]).join('\n\n');
  magicString.prepend(importBlock + '\n\n');

  return {
    code: magicString.toString(),
    map: sourceMap ? magicString.generateMap() : null
  };
}
