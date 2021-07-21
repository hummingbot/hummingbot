import { attachScopes, createFilter } from 'rollup-pluginutils';
import { walk } from 'estree-walker';
import { parse } from 'acorn';
import MagicString from 'magic-string';
import { join, relative, dirname } from 'path';
import { randomBytes } from 'crypto';

var reservedWords = 'break case class catch const continue debugger default delete do else export extends finally for function if import in instanceof let new return super switch this throw try typeof var void while with yield enum await implements package protected static interface private public'.split(' ');
var builtins = 'Infinity NaN undefined null true false eval uneval isFinite isNaN parseFloat parseInt decodeURI decodeURIComponent encodeURI encodeURIComponent escape unescape Object Function Boolean Symbol Error EvalError InternalError RangeError ReferenceError SyntaxError TypeError URIError Number Math Date String RegExp Array Int8Array Uint8Array Uint8ClampedArray Int16Array Uint16Array Int32Array Uint32Array Float32Array Float64Array Map Set WeakMap WeakSet SIMD ArrayBuffer DataView JSON Promise Generator GeneratorFunction Reflect Proxy Intl'.split(' ');

var blacklisted = Object.create(null);
reservedWords.concat(builtins).forEach(function (word) {
	return blacklisted[word] = true;
});

function makeLegalIdentifier(str) {
	str = str.replace(/-(\w)/g, function (_, letter) {
		return letter.toUpperCase();
	}).replace(/[^$_a-zA-Z0-9]/g, '_');

	if (/\d/.test(str[0]) || blacklisted[str]) str = '_' + str;

	return str;
}

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
  var name = void 0;
  var parts = [];

  while (node.type === 'MemberExpression') {
    parts.unshift(node.property.name);
    node = node.object;
  }

  name = node.name;
  parts.unshift(name);

  return {
    name: name,
    keypath: parts.join('.')
  };
}

function inject (code, id, mod1, mod2, sourceMap) {
  var ast = void 0;

  try {
    ast = parse(code, {
      ecmaVersion: 9,
      sourceType: 'module'
    });
  } catch (err) {
    err.message += ' in ' + id;
    throw err;
  }
  // analyse scopes
  var scope = attachScopes(ast, 'scope');

  var imports = {};
  ast.body.forEach(function (node) {
    if (node.type === 'ImportDeclaration') {
      node.specifiers.forEach(function (specifier) {
        imports[specifier.local.name] = true;
      });
    }
  });

  var magicString = new MagicString(code);

  var newImports = {};

  function handleReference(node, name, keypath, parent) {
    if ((mod1.has(keypath) || mod2.has(keypath)) && !scope.contains(name) && !imports[name]) {
      if (mod2.has(keypath) && parent.__handled) {
        return;
      }
      var module = mod1.has(keypath) ? mod1.get(keypath) : mod2.get(keypath);
      var moduleName = void 0,
          hash = void 0;
      if (typeof module === 'string') {
        moduleName = module;
        hash = keypath + ':' + moduleName + ':default';
      } else {
        moduleName = module[0];
        hash = keypath + ':' + moduleName + ':' + module[1];
      }
      // prevent module from importing itself
      if (moduleName === id) return;

      var importLocalName = name === keypath ? name : makeLegalIdentifier('$inject_' + keypath);

      if (!newImports[hash]) {
        newImports[hash] = 'import ' + (typeof module === 'string' ? importLocalName : '{ ' + module[1] + ' as ' + importLocalName + ' }') + ' from ' + JSON.stringify(moduleName) + ';';
      }

      if (name !== keypath) {
        magicString.overwrite(node.start, node.end, importLocalName, { storeName: true });
      }
      if (mod1.has(keypath)) {
        node.__handled = true;
      }
    }
  }

  walk(ast, {
    enter: function enter(node, parent) {
      if (sourceMap) {
        magicString.addSourcemapLocation(node.start);
        magicString.addSourcemapLocation(node.end);
      }

      if (node.scope) scope = node.scope;

      // special case – shorthand properties. because node.key === node.value,
      // we can't differentiate once we've descended into the node
      if (node.type === 'Property' && node.shorthand) {
        var name = node.key.name;
        handleReference(node, name, name);
        return this.skip();
      }

      if (isReference(node, parent)) {
        var _flatten = flatten(node),
            _name = _flatten.name,
            keypath = _flatten.keypath;

        handleReference(node, _name, keypath, parent);
      }
    },
    leave: function leave(node) {
      if (node.scope) scope = scope.parent;
    }
  });

  var keys = Object.keys(newImports);
  if (!keys.length) return null;

  var importBlock = keys.map(function (hash) {
    return newImports[hash];
  }).join('\n\n');
  magicString.prepend(importBlock + '\n\n');

  return {
    code: magicString.toString(),
    map: sourceMap ? magicString.generateMap() : null
  };
}

var PROCESS_PATH = require.resolve('process-es6');
var BUFFER_PATH = require.resolve('buffer-es6');
var GLOBAL_PATH = join(__dirname, '..', 'src', 'global.js');
var BROWSER_PATH = join(__dirname, '..', 'src', 'browser.js');
var DIRNAME = '\0node-globals:dirname';
var FILENAME = '\0node-globals:filename';

function clone(obj) {
  var out = {};
  Object.keys(obj).forEach(function (key) {
    if (Array.isArray(obj[key])) {
      out[key] = obj[key].slice();
    } else {
      out[key] = obj[key];
    }
  });
  return out;
}

var getMods = function getMods(options) {
  var _mods1 = {};
  var _mods2 = {};

  if (options.global !== false || options.process !== false) {
    _mods2.global = GLOBAL_PATH;
  }

  if (options.process !== false) {
    _mods1['process.nextTick'] = [PROCESS_PATH, 'nextTick'];
    _mods1['process.browser'] = [BROWSER_PATH, 'browser'];
    _mods2.process = PROCESS_PATH;
  }

  if (options.buffer !== false) {
    _mods1['Buffer.isBuffer'] = [BUFFER_PATH, 'isBuffer'];
    _mods2.Buffer = [BUFFER_PATH, 'Buffer'];
  }

  if (options.filename !== false) {
    _mods2.__filename = FILENAME;
  }

  if (options.dirname !== false) {
    _mods2.__dirname = DIRNAME;
  }

  var mods1 = new Map();
  var mods2 = new Map();

  Object.keys(_mods1).forEach(function (key) {
    mods1.set(key, _mods1[key]);
  });

  Object.keys(_mods2).forEach(function (key) {
    mods2.set(key, _mods2[key]);
  });

  var mods = Object.keys(_mods1).concat(Object.keys(_mods2));
  var firstpass = new RegExp('(?:' + mods.map(escape).join('|') + ')', 'g');

  return { mods1: mods1, mods2: mods2, firstpass: firstpass };
};

var escape = function escape(str) {
  return str.replace(/[\-\[\]\/\{\}\(\)\*\+\?\.\\\^\$\|]/g, '\\$&');
};

function nodeGlobals(options) {
  options = options || {};
  var basedir = options.baseDir || '/';
  var dirs = new Map();
  var opts = clone(options);
  var exclude = (opts.exclude || []).concat(GLOBAL_PATH);
  var filter = createFilter(options.include, exclude);
  var sourceMap = options.sourceMap !== false;

  var _getMods = getMods(options),
      mods1 = _getMods.mods1,
      mods2 = _getMods.mods2,
      firstpass = _getMods.firstpass;

  var buf = new Map();
  buf.set('global', GLOBAL_PATH);

  return {
    load: function load(id) {
      if (dirs.has(id)) {
        return 'export default \'' + dirs.get(id) + '\'';
      }
    },
    resolveId: function resolveId(importee, importer) {
      if (importee === DIRNAME) {
        var id = randomBytes(15).toString('hex');
        dirs.set(id, dirname('/' + relative(basedir, importer)));
        return id;
      }
      if (importee === FILENAME) {
        var _id = randomBytes(15).toString('hex');
        dirs.set(_id, '/' + relative(basedir, importer));
        return _id;
      }
    },
    transform: function transform(code, id) {
      if (id === BUFFER_PATH) {
        return inject(code, id, buf, new Map(), sourceMap);
      }
      if (!filter(id)) return null;
      if (code.search(firstpass) === -1) return null;
      if (id.slice(-3) !== '.js') return null;

      var out = inject(code, id, mods1, mods2, sourceMap);
      return out;
    }
  };
}

export default nodeGlobals;
