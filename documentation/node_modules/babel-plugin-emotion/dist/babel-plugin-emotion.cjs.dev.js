'use strict';

Object.defineProperty(exports, '__esModule', { value: true });

function _interopDefault (ex) { return (ex && (typeof ex === 'object') && 'default' in ex) ? ex['default'] : ex; }

var nodePath = _interopDefault(require('path'));
var sourceMap = require('source-map');
var convert = _interopDefault(require('convert-source-map'));
var findRoot = _interopDefault(require('find-root'));
var memoize = _interopDefault(require('@emotion/memoize'));
var hashString = _interopDefault(require('@emotion/hash'));
var escapeRegexp = _interopDefault(require('escape-string-regexp'));
var serialize = require('@emotion/serialize');
var helperModuleImports = require('@babel/helper-module-imports');
var babelPluginMacros = require('babel-plugin-macros');

// babel-plugin-styled-components
// https://github.com/styled-components/babel-plugin-styled-components/blob/8d44acc36f067d60d4e09f9c22ff89695bc332d2/src/minify/index.js
var multilineCommentRegex = /\/\*[^!](.|[\r\n])*?\*\//g;
var lineCommentStart = /\/\//g;
var symbolRegex = /(\s*[;:{},]\s*)/g; // Counts occurences of substr inside str

var countOccurences = function countOccurences(str, substr) {
  return str.split(substr).length - 1;
}; // Joins substrings until predicate returns true


var reduceSubstr = function reduceSubstr(substrs, join, predicate) {
  var length = substrs.length;
  var res = substrs[0];

  if (length === 1) {
    return res;
  }

  for (var i = 1; i < length; i++) {
    if (predicate(res)) {
      break;
    }

    res += join + substrs[i];
  }

  return res;
}; // Joins at comment starts when it's inside a string or parantheses
// effectively removing line comments


var stripLineComment = function stripLineComment(line) {
  return reduceSubstr(line.split(lineCommentStart), '//', function (str) {
    return !str.endsWith(':') && // NOTE: This is another guard against urls, if they're not inside strings or parantheses.
    countOccurences(str, "'") % 2 === 0 && countOccurences(str, '"') % 2 === 0 && countOccurences(str, '(') === countOccurences(str, ')');
  });
};
var compressSymbols = function compressSymbols(code) {
  return code.split(symbolRegex).reduce(function (str, fragment, index) {
    // Even-indices are non-symbol fragments
    if (index % 2 === 0) {
      return str + fragment;
    } // Only manipulate symbols outside of strings


    if (countOccurences(str, "'") % 2 === 0 && countOccurences(str, '"') % 2 === 0) {
      return str + fragment.trim();
    }

    return str + fragment;
  }, '');
}; // Detects lines that are exclusively line comments

var isLineComment = function isLineComment(line) {
  return line.trim().startsWith('//');
};

var linebreakRegex = /[\r\n]\s*/g;
var spacesAndLinebreakRegex = /\s+|\n+/g;

function multilineReplacer(match) {
  // When we encounter a standard multi-line CSS comment and it contains a '@'
  // character, we keep the comment but optimize it into a single line. Some
  // Stylis plugins, such as the stylis-rtl via the cssjanus plugin, use this
  // special comment syntax to control behavior (such as: /* @noflip */).
  // We can do this with standard CSS comments because they will work with
  // compression, as opposed to non-standard single-line comments that will
  // break compressed CSS. If the comment doesn't contain '@', then we replace
  // it with a line break, which effectively removes it from the output.
  var keepComment = match.indexOf('@') > -1;

  if (keepComment) {
    return match.replace(spacesAndLinebreakRegex, ' ').trim();
  }

  return '\n';
}

var minify = function minify(code) {
  var newCode = code.replace(multilineCommentRegex, multilineReplacer) // If allowed, remove line breaks and extra space from multi-line comments so they appear on one line
  .split(linebreakRegex) // Split at newlines
  .filter(function (line) {
    return line.length > 0 && !isLineComment(line);
  }) // Removes lines containing only line comments
  .map(stripLineComment) // Remove line comments inside text
  .join(' '); // Rejoin all lines

  return compressSymbols(newCode);
};

function getExpressionsFromTemplateLiteral(node, t) {
  var raw = createRawStringFromTemplateLiteral(node);
  var minified = minify(raw);
  return replacePlaceholdersWithExpressions(minified, node.expressions || [], t);
}

var interleave = function interleave(strings, interpolations) {
  return interpolations.reduce(function (array, interp, i) {
    return array.concat([interp], strings[i + 1]);
  }, [strings[0]]);
};

function getDynamicMatches(str) {
  var re = /xxx(\d+)xxx/gm;
  var match;
  var matches = [];

  while ((match = re.exec(str)) !== null) {
    // so that flow doesn't complain
    if (match !== null) {
      matches.push({
        value: match[0],
        p1: parseInt(match[1], 10),
        index: match.index
      });
    }
  }

  return matches;
}

function replacePlaceholdersWithExpressions(str, expressions, t) {
  var matches = getDynamicMatches(str);

  if (matches.length === 0) {
    if (str === '') {
      return [];
    }

    return [t.stringLiteral(str)];
  }

  var strings = [];
  var finalExpressions = [];
  var cursor = 0;
  matches.forEach(function (_ref, i) {
    var value = _ref.value,
        p1 = _ref.p1,
        index = _ref.index;
    var preMatch = str.substring(cursor, index);
    cursor = cursor + preMatch.length + value.length;

    if (preMatch) {
      strings.push(t.stringLiteral(preMatch));
    } else if (i === 0) {
      strings.push(t.stringLiteral(''));
    }

    finalExpressions.push(expressions[p1]);

    if (i === matches.length - 1) {
      strings.push(t.stringLiteral(str.substring(index + value.length)));
    }
  });
  return interleave(strings, finalExpressions).filter(function (node) {
    return node.value !== '';
  });
}

function createRawStringFromTemplateLiteral(quasi) {
  var strs = quasi.quasis.map(function (x) {
    return x.value.cooked;
  });
  var src = strs.reduce(function (arr, str, i) {
    arr.push(str);

    if (i !== strs.length - 1) {
      arr.push("xxx" + i + "xxx");
    }

    return arr;
  }, []).join('').trim();
  return src;
}

var invalidClassNameCharacters = /[!"#$%&'()*+,./:;<=>?@[\]^`|}~{]/g;

var sanitizeLabelPart = function sanitizeLabelPart(labelPart) {
  return labelPart.trim().replace(invalidClassNameCharacters, '-');
};

function getLabel(identifierName, autoLabel, labelFormat, filename) {
  if (!identifierName || !autoLabel) return null;
  if (!labelFormat) return sanitizeLabelPart(identifierName);
  var parsedPath = nodePath.parse(filename);
  var localDirname = nodePath.basename(parsedPath.dir);
  var localFilename = parsedPath.name;

  if (localFilename === 'index') {
    localFilename = localDirname;
  }

  return labelFormat.replace(/\[local\]/gi, sanitizeLabelPart(identifierName)).replace(/\[filename\]/gi, sanitizeLabelPart(localFilename)).replace(/\[dirname\]/gi, sanitizeLabelPart(localDirname));
}

function getLabelFromPath(path, state, t) {
  return getLabel(getIdentifierName(path, t), state.opts.autoLabel === undefined ? process.env.NODE_ENV !== 'production' : state.opts.autoLabel, state.opts.labelFormat, state.file.opts.filename);
}
var pascalCaseRegex = /^[A-Z][A-Za-z]+/;

function getDeclaratorName(path, t) {
  // $FlowFixMe
  var parent = path.findParent(function (p) {
    return p.isVariableDeclarator() || p.isFunctionDeclaration() || p.isFunctionExpression() || p.isArrowFunctionExpression() || p.isObjectProperty();
  });

  if (!parent) {
    return '';
  } // we probably have a css call assigned to a variable
  // so we'll just return the variable name


  if (parent.isVariableDeclarator()) {
    if (t.isIdentifier(parent.node.id)) {
      return parent.node.id.name;
    }

    return '';
  } // we probably have an inline css prop usage


  if (parent.isFunctionDeclaration()) {
    var _name = parent.node.id.name;

    if (pascalCaseRegex.test(_name)) {
      return _name;
    }

    return '';
  } // we could also have an object property


  if (parent.isObjectProperty() && !parent.node.computed) {
    return parent.node.key.name;
  }

  var variableDeclarator = path.findParent(function (p) {
    return p.isVariableDeclarator();
  });

  if (!variableDeclarator) {
    return '';
  }

  var name = variableDeclarator.node.id.name;

  if (pascalCaseRegex.test(name)) {
    return name;
  }

  return '';
}

function getIdentifierName(path, t) {
  var classOrClassPropertyParent;

  if (t.isObjectProperty(path.parentPath) && path.parentPath.node.computed === false && (t.isIdentifier(path.parentPath.node.key) || t.isStringLiteral(path.parentPath.node.key))) {
    return path.parentPath.node.key.name || path.parentPath.node.key.value;
  }

  if (path) {
    // $FlowFixMe
    classOrClassPropertyParent = path.findParent(function (p) {
      return t.isClassProperty(p) || t.isClass(p);
    });
  }

  if (classOrClassPropertyParent) {
    if (t.isClassProperty(classOrClassPropertyParent) && classOrClassPropertyParent.node.computed === false && t.isIdentifier(classOrClassPropertyParent.node.key)) {
      return classOrClassPropertyParent.node.key.name;
    }

    if (t.isClass(classOrClassPropertyParent) && classOrClassPropertyParent.node.id) {
      return t.isIdentifier(classOrClassPropertyParent.node.id) ? classOrClassPropertyParent.node.id.name : '';
    }
  }

  var declaratorName = getDeclaratorName(path, t); // if the name starts with _ it was probably generated by babel so we should ignore it

  if (declaratorName.charAt(0) === '_') {
    return '';
  }

  return declaratorName;
}

function getGeneratorOpts(file) {
  return file.opts.generatorOpts ? file.opts.generatorOpts : file.opts;
}

function makeSourceMapGenerator(file) {
  var generatorOpts = getGeneratorOpts(file);
  var filename = generatorOpts.sourceFileName;
  var generator = new sourceMap.SourceMapGenerator({
    file: filename,
    sourceRoot: generatorOpts.sourceRoot
  });
  generator.setSourceContent(filename, file.code);
  return generator;
}
function getSourceMap(offset, state) {
  var generator = makeSourceMapGenerator(state.file);
  var generatorOpts = getGeneratorOpts(state.file);

  if (generatorOpts.sourceFileName && generatorOpts.sourceFileName !== 'unknown') {
    generator.addMapping({
      generated: {
        line: 1,
        column: 0
      },
      source: generatorOpts.sourceFileName,
      original: offset
    });
    return convert.fromObject(generator).toComment({
      multiline: true
    });
  }

  return '';
}

var hashArray = function hashArray(arr) {
  return hashString(arr.join(''));
};

var unsafeRequire = require;
var getPackageRootPath = memoize(function (filename) {
  return findRoot(filename);
});
var separator = new RegExp(escapeRegexp(nodePath.sep), 'g');

var normalizePath = function normalizePath(path) {
  return nodePath.normalize(path).replace(separator, '/');
};

function getTargetClassName(state, t) {
  if (state.emotionTargetClassNameCount === undefined) {
    state.emotionTargetClassNameCount = 0;
  }

  var hasFilepath = state.file.opts.filename && state.file.opts.filename !== 'unknown';
  var filename = hasFilepath ? state.file.opts.filename : ''; // normalize the file path to ignore folder structure
  // outside the current node project and arch-specific delimiters

  var moduleName = '';
  var rootPath = filename;

  try {
    rootPath = getPackageRootPath(filename);
    moduleName = unsafeRequire(rootPath + '/package.json').name;
  } catch (err) {}

  var finalPath = filename === rootPath ? 'root' : filename.slice(rootPath.length);
  var positionInFile = state.emotionTargetClassNameCount++;
  var stuffToHash = [moduleName];

  if (finalPath) {
    stuffToHash.push(normalizePath(finalPath));
  } else {
    stuffToHash.push(state.file.code);
  }

  var stableClassName = "e" + hashArray(stuffToHash) + positionInFile;
  return stableClassName;
}

// it's meant to simplify the most common cases so i don't want to make it especially complex
// also, this will be unnecessary when prepack is ready

function simplifyObject(node, t) {
  var finalString = '';

  for (var i = 0; i < node.properties.length; i++) {
    var _ref;

    var property = node.properties[i];

    if (!t.isObjectProperty(property) || property.computed || !t.isIdentifier(property.key) && !t.isStringLiteral(property.key) || !t.isStringLiteral(property.value) && !t.isNumericLiteral(property.value) && !t.isObjectExpression(property.value)) {
      return node;
    }

    var key = property.key.name || property.key.value;

    if (key === 'styles') {
      return node;
    }

    if (t.isObjectExpression(property.value)) {
      var simplifiedChild = simplifyObject(property.value, t);

      if (!t.isStringLiteral(simplifiedChild)) {
        return node;
      }

      finalString += key + "{" + simplifiedChild.value + "}";
      continue;
    }

    var value = property.value.value;
    finalString += serialize.serializeStyles([(_ref = {}, _ref[key] = value, _ref)]).styles;
  }

  return t.stringLiteral(finalString);
}

// this only works correctly in modules, but we don't run on scripts anyway, so it's fine
// the difference is that in modules template objects are being cached per call site
function getTypeScriptMakeTemplateObjectPath(path) {
  if (path.node.arguments.length === 0) {
    return null;
  }

  var firstArgPath = path.get('arguments')[0];

  if (firstArgPath.isLogicalExpression() && firstArgPath.get('left').isIdentifier() && firstArgPath.get('right').isAssignmentExpression() && firstArgPath.get('right.right').isCallExpression() && firstArgPath.get('right.right.callee').isIdentifier() && firstArgPath.node.right.right.callee.name.includes('makeTemplateObject') && firstArgPath.node.right.right.arguments.length === 2) {
    return firstArgPath.get('right.right');
  }

  return null;
} // this is only used to prevent appending strings/expressions to arguments incorectly
// we could push them to found array expressions, as we do it for TS-transpile output ¯\_(ツ)_/¯
// it seems overly complicated though - mainly because we'd also have to check against existing stuff of a particular type (source maps & labels)
// considering Babel double-transpilation as a valid use case seems rather far-fetched

function isTaggedTemplateTranspiledByBabel(path) {
  if (path.node.arguments.length === 0) {
    return false;
  }

  var firstArgPath = path.get('arguments')[0];

  if (!firstArgPath.isCallExpression() || !firstArgPath.get('callee').isIdentifier()) {
    return false;
  }

  var calleeName = firstArgPath.node.callee.name;

  if (!calleeName.includes('templateObject')) {
    return false;
  }

  var bindingPath = path.scope.getBinding(calleeName).path;

  if (!bindingPath.isFunction()) {
    return false;
  }

  var functionBody = bindingPath.get('body.body');

  if (!functionBody[0].isVariableDeclaration()) {
    return false;
  }

  var declarationInit = functionBody[0].get('declarations')[0].get('init');

  if (!declarationInit.isCallExpression()) {
    return false;
  }

  var declarationInitArguments = declarationInit.get('arguments');

  if (declarationInitArguments.length === 0 || declarationInitArguments.length > 2 || declarationInitArguments.some(function (argPath) {
    return !argPath.isArrayExpression();
  })) {
    return false;
  }

  return true;
}

var appendStringToArguments = function appendStringToArguments(path, string, t) {
  if (!string) {
    return;
  }

  var args = path.node.arguments;

  if (t.isStringLiteral(args[args.length - 1])) {
    args[args.length - 1].value += string;
  } else {
    var makeTemplateObjectCallPath = getTypeScriptMakeTemplateObjectPath(path);

    if (makeTemplateObjectCallPath) {
      makeTemplateObjectCallPath.get('arguments').forEach(function (argPath) {
        var elements = argPath.get('elements');
        var lastElement = elements[elements.length - 1];
        lastElement.replaceWith(t.stringLiteral(lastElement.node.value + string));
      });
    } else if (!isTaggedTemplateTranspiledByBabel(path)) {
      args.push(t.stringLiteral(string));
    }
  }
};
var joinStringLiterals = function joinStringLiterals(expressions, t) {
  return expressions.reduce(function (finalExpressions, currentExpression, i) {
    if (!t.isStringLiteral(currentExpression)) {
      finalExpressions.push(currentExpression);
    } else if (t.isStringLiteral(finalExpressions[finalExpressions.length - 1])) {
      finalExpressions[finalExpressions.length - 1].value += currentExpression.value;
    } else {
      finalExpressions.push(currentExpression);
    }

    return finalExpressions;
  }, []);
};

var CSS_OBJECT_STRINGIFIED_ERROR = "You have tried to stringify object returned from `css` function. It isn't supposed to be used directly (e.g. as value of the `className` prop), but rather handed to emotion so it can handle it (e.g. as value of `css` prop)."; // with babel@6 fallback

var cloneNode = function cloneNode(t, node) {
  return typeof t.cloneNode === 'function' ? t.cloneNode(node) : t.cloneDeep(node);
};

function createSourceMapConditional(t, production, development) {
  return t.conditionalExpression(t.binaryExpression('===', t.memberExpression(t.memberExpression(t.identifier('process'), t.identifier('env')), t.identifier('NODE_ENV')), t.stringLiteral('production')), production, development);
}

var transformExpressionWithStyles = function transformExpressionWithStyles(_ref) {
  var babel = _ref.babel,
      state = _ref.state,
      path = _ref.path,
      shouldLabel = _ref.shouldLabel,
      _ref$sourceMap = _ref.sourceMap,
      sourceMap = _ref$sourceMap === void 0 ? '' : _ref$sourceMap;
  var t = babel.types;

  if (t.isTaggedTemplateExpression(path)) {
    var expressions = getExpressionsFromTemplateLiteral(path.node.quasi, t);

    if (state.emotionSourceMap && path.node.quasi.loc !== undefined) {
      sourceMap = getSourceMap(path.node.quasi.loc.start, state);
    }

    path.replaceWith(t.callExpression(path.node.tag, expressions));
  }

  if (t.isCallExpression(path)) {
    var canAppendStrings = path.node.arguments.every(function (arg) {
      return arg.type !== 'SpreadElement';
    });

    if (canAppendStrings && shouldLabel) {
      var label = getLabelFromPath(path, state, t);

      if (label) {
        appendStringToArguments(path, ";label:" + label + ";", t);
      }
    }

    path.get('arguments').forEach(function (node) {
      if (t.isObjectExpression(node)) {
        node.replaceWith(simplifyObject(node.node, t));
      }
    });
    path.node.arguments = joinStringLiterals(path.node.arguments, t);

    if (canAppendStrings && state.emotionSourceMap && !sourceMap && path.node.loc !== undefined) {
      sourceMap = getSourceMap(path.node.loc.start, state);
    }

    if (path.node.arguments.length === 1 && t.isStringLiteral(path.node.arguments[0])) {
      var cssString = path.node.arguments[0].value;
      var res = serialize.serializeStyles([cssString]);
      var prodNode = t.objectExpression([t.objectProperty(t.identifier('name'), t.stringLiteral(res.name)), t.objectProperty(t.identifier('styles'), t.stringLiteral(res.styles))]);
      var node = prodNode;

      if (sourceMap) {
        if (!state.emotionStringifiedCssId) {
          var uid = state.file.scope.generateUidIdentifier('__EMOTION_STRINGIFIED_CSS_ERROR__');
          state.emotionStringifiedCssId = uid;
          var cssObjectToString = t.functionDeclaration(uid, [], t.blockStatement([t.returnStatement(t.stringLiteral(CSS_OBJECT_STRINGIFIED_ERROR))]));
          cssObjectToString._compact = true;
          state.file.path.unshiftContainer('body', [cssObjectToString]);
        }

        var devNode = t.objectExpression([t.objectProperty(t.identifier('name'), t.stringLiteral(res.name)), t.objectProperty(t.identifier('styles'), t.stringLiteral(res.styles)), t.objectProperty(t.identifier('map'), t.stringLiteral(sourceMap)), t.objectProperty(t.identifier('toString'), cloneNode(t, state.emotionStringifiedCssId))]);
        node = createSourceMapConditional(t, prodNode, devNode);
      }

      return node;
    }

    if (sourceMap) {
      var lastIndex = path.node.arguments.length - 1;
      var last = path.node.arguments[lastIndex];
      var sourceMapConditional = createSourceMapConditional(t, t.stringLiteral(''), t.stringLiteral(sourceMap));

      if (t.isStringLiteral(last)) {
        path.node.arguments[lastIndex] = t.binaryExpression('+', last, sourceMapConditional);
      } else {
        var makeTemplateObjectCallPath = getTypeScriptMakeTemplateObjectPath(path);

        if (makeTemplateObjectCallPath) {
          var sourceMapId = state.file.scope.generateUidIdentifier('emotionSourceMap');
          var sourceMapDeclaration = t.variableDeclaration('var', [t.variableDeclarator(sourceMapId, sourceMapConditional)]);
          sourceMapDeclaration._compact = true;
          state.file.path.unshiftContainer('body', [sourceMapDeclaration]);
          makeTemplateObjectCallPath.get('arguments').forEach(function (argPath) {
            var elements = argPath.get('elements');
            var lastElement = elements[elements.length - 1];
            lastElement.replaceWith(t.binaryExpression('+', lastElement.node, cloneNode(t, sourceMapId)));
          });
        } else if (!isTaggedTemplateTranspiledByBabel(path)) {
          path.node.arguments.push(sourceMapConditional);
        }
      }
    }
  }
};

var getKnownProperties = function getKnownProperties(t, node) {
  return new Set(node.properties.filter(function (n) {
    return t.isObjectProperty(n) && !n.computed;
  }).map(function (n) {
    return t.isIdentifier(n.key) ? n.key.name : n.key.value;
  }));
};

var getStyledOptions = function getStyledOptions(t, path, state) {
  var args = path.node.arguments;
  var optionsArgument = args.length >= 2 ? args[1] : null;
  var properties = [];
  var knownProperties = optionsArgument && t.isObjectExpression(optionsArgument) ? getKnownProperties(t, optionsArgument) : new Set();

  if (!knownProperties.has('target')) {
    properties.push(t.objectProperty(t.identifier('target'), t.stringLiteral(getTargetClassName(state))));
  }

  var label = getLabelFromPath(path, state, t);

  if (label && !knownProperties.has('label')) {
    properties.push(t.objectProperty(t.identifier('label'), t.stringLiteral(label)));
  }

  if (optionsArgument) {
    if (!t.isObjectExpression(optionsArgument)) {
      return t.callExpression(state.file.addHelper('extends'), [t.objectExpression([]), t.objectExpression(properties), optionsArgument]);
    }

    properties.unshift.apply(properties, optionsArgument.properties);
  }

  return t.objectExpression( // $FlowFixMe
  properties);
};

var createEmotionMacro = function createEmotionMacro(instancePath) {
  return babelPluginMacros.createMacro(function macro(_ref) {
    var references = _ref.references,
        state = _ref.state,
        babel = _ref.babel,
        isEmotionCall = _ref.isEmotionCall;

    if (!isEmotionCall) {
      state.emotionSourceMap = true;
    }

    var t = babel.types;
    Object.keys(references).forEach(function (referenceKey) {
      var isPure = true;
      var runtimeNode = helperModuleImports.addNamed(state.file.path, referenceKey, instancePath);

      switch (referenceKey) {
        case 'injectGlobal':
          {
            isPure = false;
          }
        // eslint-disable-next-line no-fallthrough

        case 'css':
        case 'keyframes':
          {
            references[referenceKey].reverse().forEach(function (reference) {
              var path = reference.parentPath;
              reference.replaceWith(t.cloneDeep(runtimeNode));

              if (isPure) {
                path.addComment('leading', '#__PURE__');
              }

              var node = transformExpressionWithStyles({
                babel: babel,
                state: state,
                path: path,
                shouldLabel: true
              });

              if (node) {
                path.node.arguments[0] = node;
              }
            });
            break;
          }

        default:
          {
            references[referenceKey].reverse().forEach(function (reference) {
              reference.replaceWith(t.cloneDeep(runtimeNode));
            });
          }
      }
    });
  });
};

var createStyledMacro = function createStyledMacro(_ref) {
  var importPath = _ref.importPath,
      _ref$originalImportPa = _ref.originalImportPath,
      originalImportPath = _ref$originalImportPa === void 0 ? importPath : _ref$originalImportPa,
      isWeb = _ref.isWeb;
  return babelPluginMacros.createMacro(function (_ref2) {
    var references = _ref2.references,
        state = _ref2.state,
        babel = _ref2.babel,
        isEmotionCall = _ref2.isEmotionCall;

    if (!isEmotionCall) {
      state.emotionSourceMap = true;
    }

    var t = babel.types;

    if (references["default"] && references["default"].length) {
      var _styledIdentifier;

      var getStyledIdentifier = function getStyledIdentifier() {
        if (_styledIdentifier === undefined) {
          _styledIdentifier = helperModuleImports.addDefault(state.file.path, importPath, {
            nameHint: 'styled'
          });
        }

        return t.cloneDeep(_styledIdentifier);
      };

      var originalImportPathStyledIdentifier;

      var getOriginalImportPathStyledIdentifier = function getOriginalImportPathStyledIdentifier() {
        if (originalImportPathStyledIdentifier === undefined) {
          originalImportPathStyledIdentifier = helperModuleImports.addDefault(state.file.path, originalImportPath, {
            nameHint: 'styled'
          });
        }

        return t.cloneDeep(originalImportPathStyledIdentifier);
      };

      if (importPath === originalImportPath) {
        getOriginalImportPathStyledIdentifier = getStyledIdentifier;
      }

      references["default"].forEach(function (reference) {
        var isCall = false;

        if (t.isMemberExpression(reference.parent) && reference.parent.computed === false) {
          isCall = true;

          if ( // checks if the first character is lowercase
          // becasue we don't want to transform the member expression if
          // it's in primitives/native
          reference.parent.property.name.charCodeAt(0) > 96) {
            reference.parentPath.replaceWith(t.callExpression(getStyledIdentifier(), [t.stringLiteral(reference.parent.property.name)]));
          } else {
            reference.replaceWith(getStyledIdentifier());
          }
        } else if (reference.parentPath && reference.parentPath.parentPath && t.isCallExpression(reference.parentPath) && reference.parent.callee === reference.node) {
          isCall = true;
          reference.replaceWith(getStyledIdentifier());
        } else {
          reference.replaceWith(getOriginalImportPathStyledIdentifier());
        }

        if (reference.parentPath && reference.parentPath.parentPath) {
          var styledCallPath = reference.parentPath.parentPath;
          var node = transformExpressionWithStyles({
            path: styledCallPath,
            state: state,
            babel: babel,
            shouldLabel: false
          });

          if (node && isWeb) {
            // we know the argument length will be 1 since that's the only time we will have a node since it will be static
            styledCallPath.node.arguments[0] = node;
          }
        }

        if (isCall) {
          reference.addComment('leading', '#__PURE__');

          if (isWeb) {
            reference.parentPath.node.arguments[1] = getStyledOptions(t, reference.parentPath, state);
          }
        }
      });
    }

    Object.keys(references).filter(function (x) {
      return x !== 'default';
    }).forEach(function (referenceKey) {
      var runtimeNode = helperModuleImports.addNamed(state.file.path, referenceKey, importPath);
      references[referenceKey].reverse().forEach(function (reference) {
        reference.replaceWith(t.cloneDeep(runtimeNode));
      });
    });
  });
};

var transformCssCallExpression = function transformCssCallExpression(_ref) {
  var babel = _ref.babel,
      state = _ref.state,
      path = _ref.path,
      sourceMap = _ref.sourceMap;
  var node = transformExpressionWithStyles({
    babel: babel,
    state: state,
    path: path,
    shouldLabel: true,
    sourceMap: sourceMap
  });

  if (node) {
    path.replaceWith(node);
    path.hoist();
  } else if (path.isCallExpression()) {
    path.addComment('leading', '#__PURE__');
  }
};
var cssMacro = babelPluginMacros.createMacro(function (_ref2) {
  var references = _ref2.references,
      state = _ref2.state,
      babel = _ref2.babel,
      isEmotionCall = _ref2.isEmotionCall;

  if (!isEmotionCall) {
    state.emotionSourceMap = true;
  }

  var t = babel.types;

  if (references["default"] && references["default"].length) {
    references["default"].reverse().forEach(function (reference) {
      if (!state.cssIdentifier) {
        state.cssIdentifier = helperModuleImports.addDefault(reference, '@emotion/css', {
          nameHint: 'css'
        });
      }

      reference.replaceWith(t.cloneDeep(state.cssIdentifier));
      transformCssCallExpression({
        babel: babel,
        state: state,
        path: reference.parentPath
      });
    });
  }

  Object.keys(references).filter(function (x) {
    return x !== 'default';
  }).forEach(function (referenceKey) {
    var runtimeNode = helperModuleImports.addNamed(state.file.path, referenceKey, '@emotion/css', {
      nameHint: referenceKey
    });
    references[referenceKey].reverse().forEach(function (reference) {
      reference.replaceWith(t.cloneDeep(runtimeNode));
    });
  });
});

var webStyledMacro = createStyledMacro({
  importPath: '@emotion/styled-base',
  originalImportPath: '@emotion/styled',
  isWeb: true
});
var nativeStyledMacro = createStyledMacro({
  importPath: '@emotion/native',
  originalImportPath: '@emotion/native',
  isWeb: false
});
var primitivesStyledMacro = createStyledMacro({
  importPath: '@emotion/primitives',
  originalImportPath: '@emotion/primitives',
  isWeb: false
});
var macros = {
  createEmotionMacro: createEmotionMacro,
  css: cssMacro,
  createStyledMacro: createStyledMacro
};

var emotionCoreMacroThatsNotARealMacro = function emotionCoreMacroThatsNotARealMacro(_ref) {
  var references = _ref.references,
      state = _ref.state,
      babel = _ref.babel;
  Object.keys(references).forEach(function (refKey) {
    if (refKey === 'css') {
      references[refKey].forEach(function (path) {
        transformCssCallExpression({
          babel: babel,
          state: state,
          path: path.parentPath
        });
      });
    }
  });
};

emotionCoreMacroThatsNotARealMacro.keepImport = true;

function getAbsolutePath(instancePath, rootPath) {
  if (instancePath.charAt(0) === '.') {
    var absoluteInstancePath = nodePath.resolve(rootPath, instancePath);
    return absoluteInstancePath;
  }

  return false;
}

function getInstancePathToCompare(instancePath, rootPath) {
  var absolutePath = getAbsolutePath(instancePath, rootPath);

  if (absolutePath === false) {
    return instancePath;
  }

  return absolutePath;
}

function index (babel) {
  var t = babel.types;
  return {
    name: 'emotion',
    inherits: require('babel-plugin-syntax-jsx'),
    visitor: {
      ImportDeclaration: function ImportDeclaration(path, state) {
        var hasFilepath = path.hub.file.opts.filename && path.hub.file.opts.filename !== 'unknown';
        var dirname = hasFilepath ? nodePath.dirname(path.hub.file.opts.filename) : '';

        if (!state.pluginMacros[path.node.source.value] && state.emotionInstancePaths.indexOf(getInstancePathToCompare(path.node.source.value, dirname)) !== -1) {
          state.pluginMacros[path.node.source.value] = createEmotionMacro(path.node.source.value);
        }

        var pluginMacros = state.pluginMacros; // most of this is from https://github.com/kentcdodds/babel-plugin-macros/blob/master/src/index.js

        if (pluginMacros[path.node.source.value] === undefined) {
          return;
        }

        if (t.isImportNamespaceSpecifier(path.node.specifiers[0])) {
          return;
        }

        var imports = path.node.specifiers.map(function (s) {
          return {
            localName: s.local.name,
            importedName: s.type === 'ImportDefaultSpecifier' ? 'default' : s.imported.name
          };
        });
        var shouldExit = false;
        var hasReferences = false;
        var referencePathsByImportName = imports.reduce(function (byName, _ref2) {
          var importedName = _ref2.importedName,
              localName = _ref2.localName;
          var binding = path.scope.getBinding(localName);

          if (!binding) {
            shouldExit = true;
            return byName;
          }

          byName[importedName] = binding.referencePaths;
          hasReferences = hasReferences || Boolean(byName[importedName].length);
          return byName;
        }, {});

        if (!hasReferences || shouldExit) {
          return;
        }
        /**
         * Other plugins that run before babel-plugin-macros might use path.replace, where a path is
         * put into its own replacement. Apparently babel does not update the scope after such
         * an operation. As a remedy, the whole scope is traversed again with an empty "Identifier"
         * visitor - this makes the problem go away.
         *
         * See: https://github.com/kentcdodds/import-all.macro/issues/7
         */


        state.file.scope.path.traverse({
          Identifier: function Identifier() {}
        });
        pluginMacros[path.node.source.value]({
          references: referencePathsByImportName,
          state: state,
          babel: babel,
          isBabelMacrosCall: true,
          isEmotionCall: true
        });

        if (!pluginMacros[path.node.source.value].keepImport) {
          path.remove();
        }
      },
      Program: function Program(path, state) {
        state.emotionInstancePaths = (state.opts.instances || []).map(function (instancePath) {
          return getInstancePathToCompare(instancePath, process.cwd());
        });
        state.pluginMacros = {
          '@emotion/css': cssMacro,
          '@emotion/styled': webStyledMacro,
          '@emotion/core': emotionCoreMacroThatsNotARealMacro,
          '@emotion/primitives': primitivesStyledMacro,
          '@emotion/native': nativeStyledMacro,
          emotion: createEmotionMacro('emotion')
        };

        if (state.opts.cssPropOptimization === undefined) {
          for (var _iterator = path.node.body, _isArray = Array.isArray(_iterator), _i = 0, _iterator = _isArray ? _iterator : _iterator[Symbol.iterator]();;) {
            var _ref3;

            if (_isArray) {
              if (_i >= _iterator.length) break;
              _ref3 = _iterator[_i++];
            } else {
              _i = _iterator.next();
              if (_i.done) break;
              _ref3 = _i.value;
            }

            var node = _ref3;

            if (t.isImportDeclaration(node) && node.source.value === '@emotion/core' && node.specifiers.some(function (x) {
              return t.isImportSpecifier(x) && x.imported.name === 'jsx';
            })) {
              state.transformCssProp = true;
              break;
            }
          }
        } else {
          state.transformCssProp = state.opts.cssPropOptimization;
        }

        if (state.opts.sourceMap === false) {
          state.emotionSourceMap = false;
        } else {
          state.emotionSourceMap = true;
        }
      },
      JSXAttribute: function JSXAttribute(path, state) {
        if (path.node.name.name !== 'css' || !state.transformCssProp) {
          return;
        }

        if (t.isJSXExpressionContainer(path.node.value) && (t.isObjectExpression(path.node.value.expression) || t.isArrayExpression(path.node.value.expression))) {
          var expressionPath = path.get('value.expression');
          var sourceMap = state.emotionSourceMap && path.node.loc !== undefined ? getSourceMap(path.node.loc.start, state) : '';
          expressionPath.replaceWith(t.callExpression( // the name of this identifier doesn't really matter at all
          // it'll never appear in generated code
          t.identifier('___shouldNeverAppearCSS'), [path.node.value.expression]));
          transformCssCallExpression({
            babel: babel,
            state: state,
            path: expressionPath,
            sourceMap: sourceMap
          });

          if (t.isCallExpression(expressionPath)) {
            if (!state.cssIdentifier) {
              state.cssIdentifier = helperModuleImports.addDefault(path, '@emotion/css', {
                nameHint: 'css'
              });
            }

            expressionPath.get('callee').replaceWith(t.cloneDeep(state.cssIdentifier));
          }
        }
      },
      CallExpression: {
        exit: function exit(path, state) {
          try {
            if (path.node.callee && path.node.callee.property && path.node.callee.property.name === 'withComponent') {
              switch (path.node.arguments.length) {
                case 1:
                case 2:
                  {
                    path.node.arguments[1] = getStyledOptions(t, path, state);
                  }
              }
            }
          } catch (e) {
            throw path.buildCodeFrameError(e);
          }
        }
      }
    }
  };
}

exports.default = index;
exports.macros = macros;
