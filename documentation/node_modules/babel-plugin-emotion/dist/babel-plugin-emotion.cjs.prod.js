"use strict";

function _interopDefault(ex) {
  return ex && "object" == typeof ex && "default" in ex ? ex.default : ex;
}

Object.defineProperty(exports, "__esModule", {
  value: !0
});

var nodePath = _interopDefault(require("path")), sourceMap = require("source-map"), convert = _interopDefault(require("convert-source-map")), findRoot = _interopDefault(require("find-root")), memoize = _interopDefault(require("@emotion/memoize")), hashString = _interopDefault(require("@emotion/hash")), escapeRegexp = _interopDefault(require("escape-string-regexp")), serialize = require("@emotion/serialize"), helperModuleImports = require("@babel/helper-module-imports"), babelPluginMacros = require("babel-plugin-macros"), multilineCommentRegex = /\/\*[^!](.|[\r\n])*?\*\//g, lineCommentStart = /\/\//g, symbolRegex = /(\s*[;:{},]\s*)/g, countOccurences = function(str, substr) {
  return str.split(substr).length - 1;
}, reduceSubstr = function(substrs, join, predicate) {
  var length = substrs.length, res = substrs[0];
  if (1 === length) return res;
  for (var i = 1; i < length && !predicate(res); i++) res += join + substrs[i];
  return res;
}, stripLineComment = function(line) {
  return reduceSubstr(line.split(lineCommentStart), "//", function(str) {
    return !str.endsWith(":") && countOccurences(str, "'") % 2 == 0 && countOccurences(str, '"') % 2 == 0 && countOccurences(str, "(") === countOccurences(str, ")");
  });
}, compressSymbols = function(code) {
  return code.split(symbolRegex).reduce(function(str, fragment, index) {
    return index % 2 == 0 ? str + fragment : countOccurences(str, "'") % 2 == 0 && countOccurences(str, '"') % 2 == 0 ? str + fragment.trim() : str + fragment;
  }, "");
}, isLineComment = function(line) {
  return line.trim().startsWith("//");
}, linebreakRegex = /[\r\n]\s*/g, spacesAndLinebreakRegex = /\s+|\n+/g;

function multilineReplacer(match) {
  return match.indexOf("@") > -1 ? match.replace(spacesAndLinebreakRegex, " ").trim() : "\n";
}

var minify = function(code) {
  var newCode = code.replace(multilineCommentRegex, multilineReplacer).split(linebreakRegex).filter(function(line) {
    return line.length > 0 && !isLineComment(line);
  }).map(stripLineComment).join(" ");
  return compressSymbols(newCode);
};

function getExpressionsFromTemplateLiteral(node, t) {
  var raw = createRawStringFromTemplateLiteral(node);
  return replacePlaceholdersWithExpressions(minify(raw), node.expressions || [], t);
}

var interleave = function(strings, interpolations) {
  return interpolations.reduce(function(array, interp, i) {
    return array.concat([ interp ], strings[i + 1]);
  }, [ strings[0] ]);
};

function getDynamicMatches(str) {
  for (var match, re = /xxx(\d+)xxx/gm, matches = []; null !== (match = re.exec(str)); ) null !== match && matches.push({
    value: match[0],
    p1: parseInt(match[1], 10),
    index: match.index
  });
  return matches;
}

function replacePlaceholdersWithExpressions(str, expressions, t) {
  var matches = getDynamicMatches(str);
  if (0 === matches.length) return "" === str ? [] : [ t.stringLiteral(str) ];
  var strings = [], finalExpressions = [], cursor = 0;
  return matches.forEach(function(_ref, i) {
    var value = _ref.value, p1 = _ref.p1, index = _ref.index, preMatch = str.substring(cursor, index);
    cursor = cursor + preMatch.length + value.length, preMatch ? strings.push(t.stringLiteral(preMatch)) : 0 === i && strings.push(t.stringLiteral("")), 
    finalExpressions.push(expressions[p1]), i === matches.length - 1 && strings.push(t.stringLiteral(str.substring(index + value.length)));
  }), interleave(strings, finalExpressions).filter(function(node) {
    return "" !== node.value;
  });
}

function createRawStringFromTemplateLiteral(quasi) {
  var strs = quasi.quasis.map(function(x) {
    return x.value.cooked;
  });
  return strs.reduce(function(arr, str, i) {
    return arr.push(str), i !== strs.length - 1 && arr.push("xxx" + i + "xxx"), arr;
  }, []).join("").trim();
}

var invalidClassNameCharacters = /[!"#$%&'()*+,.\/:;<=>?@[\]^`|}~{]/g, sanitizeLabelPart = function(labelPart) {
  return labelPart.trim().replace(invalidClassNameCharacters, "-");
};

function getLabel(identifierName, autoLabel, labelFormat, filename) {
  if (!identifierName || !autoLabel) return null;
  if (!labelFormat) return sanitizeLabelPart(identifierName);
  var parsedPath = nodePath.parse(filename), localDirname = nodePath.basename(parsedPath.dir), localFilename = parsedPath.name;
  return "index" === localFilename && (localFilename = localDirname), labelFormat.replace(/\[local\]/gi, sanitizeLabelPart(identifierName)).replace(/\[filename\]/gi, sanitizeLabelPart(localFilename)).replace(/\[dirname\]/gi, sanitizeLabelPart(localDirname));
}

function getLabelFromPath(path, state, t) {
  return getLabel(getIdentifierName(path, t), void 0 !== state.opts.autoLabel && state.opts.autoLabel, state.opts.labelFormat, state.file.opts.filename);
}

var pascalCaseRegex = /^[A-Z][A-Za-z]+/;

function getDeclaratorName(path, t) {
  var parent = path.findParent(function(p) {
    return p.isVariableDeclarator() || p.isFunctionDeclaration() || p.isFunctionExpression() || p.isArrowFunctionExpression() || p.isObjectProperty();
  });
  if (!parent) return "";
  if (parent.isVariableDeclarator()) return t.isIdentifier(parent.node.id) ? parent.node.id.name : "";
  if (parent.isFunctionDeclaration()) {
    var _name = parent.node.id.name;
    return pascalCaseRegex.test(_name) ? _name : "";
  }
  if (parent.isObjectProperty() && !parent.node.computed) return parent.node.key.name;
  var variableDeclarator = path.findParent(function(p) {
    return p.isVariableDeclarator();
  });
  if (!variableDeclarator) return "";
  var name = variableDeclarator.node.id.name;
  return pascalCaseRegex.test(name) ? name : "";
}

function getIdentifierName(path, t) {
  var classOrClassPropertyParent;
  if (t.isObjectProperty(path.parentPath) && !1 === path.parentPath.node.computed && (t.isIdentifier(path.parentPath.node.key) || t.isStringLiteral(path.parentPath.node.key))) return path.parentPath.node.key.name || path.parentPath.node.key.value;
  if (path && (classOrClassPropertyParent = path.findParent(function(p) {
    return t.isClassProperty(p) || t.isClass(p);
  })), classOrClassPropertyParent) {
    if (t.isClassProperty(classOrClassPropertyParent) && !1 === classOrClassPropertyParent.node.computed && t.isIdentifier(classOrClassPropertyParent.node.key)) return classOrClassPropertyParent.node.key.name;
    if (t.isClass(classOrClassPropertyParent) && classOrClassPropertyParent.node.id) return t.isIdentifier(classOrClassPropertyParent.node.id) ? classOrClassPropertyParent.node.id.name : "";
  }
  var declaratorName = getDeclaratorName(path, t);
  return "_" === declaratorName.charAt(0) ? "" : declaratorName;
}

function getGeneratorOpts(file) {
  return file.opts.generatorOpts ? file.opts.generatorOpts : file.opts;
}

function makeSourceMapGenerator(file) {
  var generatorOpts = getGeneratorOpts(file), filename = generatorOpts.sourceFileName, generator = new sourceMap.SourceMapGenerator({
    file: filename,
    sourceRoot: generatorOpts.sourceRoot
  });
  return generator.setSourceContent(filename, file.code), generator;
}

function getSourceMap(offset, state) {
  var generator = makeSourceMapGenerator(state.file), generatorOpts = getGeneratorOpts(state.file);
  return generatorOpts.sourceFileName && "unknown" !== generatorOpts.sourceFileName ? (generator.addMapping({
    generated: {
      line: 1,
      column: 0
    },
    source: generatorOpts.sourceFileName,
    original: offset
  }), convert.fromObject(generator).toComment({
    multiline: !0
  })) : "";
}

var hashArray = function(arr) {
  return hashString(arr.join(""));
}, unsafeRequire = require, getPackageRootPath = memoize(function(filename) {
  return findRoot(filename);
}), separator = new RegExp(escapeRegexp(nodePath.sep), "g"), normalizePath = function(path) {
  return nodePath.normalize(path).replace(separator, "/");
};

function getTargetClassName(state, t) {
  void 0 === state.emotionTargetClassNameCount && (state.emotionTargetClassNameCount = 0);
  var filename = state.file.opts.filename && "unknown" !== state.file.opts.filename ? state.file.opts.filename : "", moduleName = "", rootPath = filename;
  try {
    rootPath = getPackageRootPath(filename), moduleName = unsafeRequire(rootPath + "/package.json").name;
  } catch (err) {}
  var finalPath = filename === rootPath ? "root" : filename.slice(rootPath.length), positionInFile = state.emotionTargetClassNameCount++, stuffToHash = [ moduleName ];
  return finalPath ? stuffToHash.push(normalizePath(finalPath)) : stuffToHash.push(state.file.code), 
  "e" + hashArray(stuffToHash) + positionInFile;
}

function simplifyObject(node, t) {
  for (var finalString = "", i = 0; i < node.properties.length; i++) {
    var _ref, property = node.properties[i];
    if (!t.isObjectProperty(property) || property.computed || !t.isIdentifier(property.key) && !t.isStringLiteral(property.key) || !t.isStringLiteral(property.value) && !t.isNumericLiteral(property.value) && !t.isObjectExpression(property.value)) return node;
    var key = property.key.name || property.key.value;
    if ("styles" === key) return node;
    if (t.isObjectExpression(property.value)) {
      var simplifiedChild = simplifyObject(property.value, t);
      if (!t.isStringLiteral(simplifiedChild)) return node;
      finalString += key + "{" + simplifiedChild.value + "}";
    } else {
      var value = property.value.value;
      finalString += serialize.serializeStyles([ (_ref = {}, _ref[key] = value, _ref) ]).styles;
    }
  }
  return t.stringLiteral(finalString);
}

function getTypeScriptMakeTemplateObjectPath(path) {
  if (0 === path.node.arguments.length) return null;
  var firstArgPath = path.get("arguments")[0];
  return firstArgPath.isLogicalExpression() && firstArgPath.get("left").isIdentifier() && firstArgPath.get("right").isAssignmentExpression() && firstArgPath.get("right.right").isCallExpression() && firstArgPath.get("right.right.callee").isIdentifier() && firstArgPath.node.right.right.callee.name.includes("makeTemplateObject") && 2 === firstArgPath.node.right.right.arguments.length ? firstArgPath.get("right.right") : null;
}

function isTaggedTemplateTranspiledByBabel(path) {
  if (0 === path.node.arguments.length) return !1;
  var firstArgPath = path.get("arguments")[0];
  if (!firstArgPath.isCallExpression() || !firstArgPath.get("callee").isIdentifier()) return !1;
  var calleeName = firstArgPath.node.callee.name;
  if (!calleeName.includes("templateObject")) return !1;
  var bindingPath = path.scope.getBinding(calleeName).path;
  if (!bindingPath.isFunction()) return !1;
  var functionBody = bindingPath.get("body.body");
  if (!functionBody[0].isVariableDeclaration()) return !1;
  var declarationInit = functionBody[0].get("declarations")[0].get("init");
  if (!declarationInit.isCallExpression()) return !1;
  var declarationInitArguments = declarationInit.get("arguments");
  return !(0 === declarationInitArguments.length || declarationInitArguments.length > 2 || declarationInitArguments.some(function(argPath) {
    return !argPath.isArrayExpression();
  }));
}

var appendStringToArguments = function(path, string, t) {
  if (string) {
    var args = path.node.arguments;
    if (t.isStringLiteral(args[args.length - 1])) args[args.length - 1].value += string; else {
      var makeTemplateObjectCallPath = getTypeScriptMakeTemplateObjectPath(path);
      makeTemplateObjectCallPath ? makeTemplateObjectCallPath.get("arguments").forEach(function(argPath) {
        var elements = argPath.get("elements"), lastElement = elements[elements.length - 1];
        lastElement.replaceWith(t.stringLiteral(lastElement.node.value + string));
      }) : isTaggedTemplateTranspiledByBabel(path) || args.push(t.stringLiteral(string));
    }
  }
}, joinStringLiterals = function(expressions, t) {
  return expressions.reduce(function(finalExpressions, currentExpression, i) {
    return t.isStringLiteral(currentExpression) && t.isStringLiteral(finalExpressions[finalExpressions.length - 1]) ? finalExpressions[finalExpressions.length - 1].value += currentExpression.value : finalExpressions.push(currentExpression), 
    finalExpressions;
  }, []);
}, CSS_OBJECT_STRINGIFIED_ERROR = "You have tried to stringify object returned from `css` function. It isn't supposed to be used directly (e.g. as value of the `className` prop), but rather handed to emotion so it can handle it (e.g. as value of `css` prop).", cloneNode = function(t, node) {
  return "function" == typeof t.cloneNode ? t.cloneNode(node) : t.cloneDeep(node);
};

function createSourceMapConditional(t, production, development) {
  return t.conditionalExpression(t.binaryExpression("===", t.memberExpression(t.memberExpression(t.identifier("process"), t.identifier("env")), t.identifier("NODE_ENV")), t.stringLiteral("production")), production, development);
}

var transformExpressionWithStyles = function(_ref) {
  var babel = _ref.babel, state = _ref.state, path = _ref.path, shouldLabel = _ref.shouldLabel, _ref$sourceMap = _ref.sourceMap, sourceMap = void 0 === _ref$sourceMap ? "" : _ref$sourceMap, t = babel.types;
  if (t.isTaggedTemplateExpression(path)) {
    var expressions = getExpressionsFromTemplateLiteral(path.node.quasi, t);
    state.emotionSourceMap && void 0 !== path.node.quasi.loc && (sourceMap = getSourceMap(path.node.quasi.loc.start, state)), 
    path.replaceWith(t.callExpression(path.node.tag, expressions));
  }
  if (t.isCallExpression(path)) {
    var canAppendStrings = path.node.arguments.every(function(arg) {
      return "SpreadElement" !== arg.type;
    });
    if (canAppendStrings && shouldLabel) {
      var label = getLabelFromPath(path, state, t);
      label && appendStringToArguments(path, ";label:" + label + ";", t);
    }
    if (path.get("arguments").forEach(function(node) {
      t.isObjectExpression(node) && node.replaceWith(simplifyObject(node.node, t));
    }), path.node.arguments = joinStringLiterals(path.node.arguments, t), canAppendStrings && state.emotionSourceMap && !sourceMap && void 0 !== path.node.loc && (sourceMap = getSourceMap(path.node.loc.start, state)), 
    1 === path.node.arguments.length && t.isStringLiteral(path.node.arguments[0])) {
      var cssString = path.node.arguments[0].value, res = serialize.serializeStyles([ cssString ]), prodNode = t.objectExpression([ t.objectProperty(t.identifier("name"), t.stringLiteral(res.name)), t.objectProperty(t.identifier("styles"), t.stringLiteral(res.styles)) ]), node = prodNode;
      if (sourceMap) {
        if (!state.emotionStringifiedCssId) {
          var uid = state.file.scope.generateUidIdentifier("__EMOTION_STRINGIFIED_CSS_ERROR__");
          state.emotionStringifiedCssId = uid;
          var cssObjectToString = t.functionDeclaration(uid, [], t.blockStatement([ t.returnStatement(t.stringLiteral(CSS_OBJECT_STRINGIFIED_ERROR)) ]));
          cssObjectToString._compact = !0, state.file.path.unshiftContainer("body", [ cssObjectToString ]);
        }
        var devNode = t.objectExpression([ t.objectProperty(t.identifier("name"), t.stringLiteral(res.name)), t.objectProperty(t.identifier("styles"), t.stringLiteral(res.styles)), t.objectProperty(t.identifier("map"), t.stringLiteral(sourceMap)), t.objectProperty(t.identifier("toString"), cloneNode(t, state.emotionStringifiedCssId)) ]);
        node = createSourceMapConditional(t, prodNode, devNode);
      }
      return node;
    }
    if (sourceMap) {
      var lastIndex = path.node.arguments.length - 1, last = path.node.arguments[lastIndex], sourceMapConditional = createSourceMapConditional(t, t.stringLiteral(""), t.stringLiteral(sourceMap));
      if (t.isStringLiteral(last)) path.node.arguments[lastIndex] = t.binaryExpression("+", last, sourceMapConditional); else {
        var makeTemplateObjectCallPath = getTypeScriptMakeTemplateObjectPath(path);
        if (makeTemplateObjectCallPath) {
          var sourceMapId = state.file.scope.generateUidIdentifier("emotionSourceMap"), sourceMapDeclaration = t.variableDeclaration("var", [ t.variableDeclarator(sourceMapId, sourceMapConditional) ]);
          sourceMapDeclaration._compact = !0, state.file.path.unshiftContainer("body", [ sourceMapDeclaration ]), 
          makeTemplateObjectCallPath.get("arguments").forEach(function(argPath) {
            var elements = argPath.get("elements"), lastElement = elements[elements.length - 1];
            lastElement.replaceWith(t.binaryExpression("+", lastElement.node, cloneNode(t, sourceMapId)));
          });
        } else isTaggedTemplateTranspiledByBabel(path) || path.node.arguments.push(sourceMapConditional);
      }
    }
  }
}, getKnownProperties = function(t, node) {
  return new Set(node.properties.filter(function(n) {
    return t.isObjectProperty(n) && !n.computed;
  }).map(function(n) {
    return t.isIdentifier(n.key) ? n.key.name : n.key.value;
  }));
}, getStyledOptions = function(t, path, state) {
  var args = path.node.arguments, optionsArgument = args.length >= 2 ? args[1] : null, properties = [], knownProperties = optionsArgument && t.isObjectExpression(optionsArgument) ? getKnownProperties(t, optionsArgument) : new Set();
  knownProperties.has("target") || properties.push(t.objectProperty(t.identifier("target"), t.stringLiteral(getTargetClassName(state))));
  var label = getLabelFromPath(path, state, t);
  if (label && !knownProperties.has("label") && properties.push(t.objectProperty(t.identifier("label"), t.stringLiteral(label))), 
  optionsArgument) {
    if (!t.isObjectExpression(optionsArgument)) return t.callExpression(state.file.addHelper("extends"), [ t.objectExpression([]), t.objectExpression(properties), optionsArgument ]);
    properties.unshift.apply(properties, optionsArgument.properties);
  }
  return t.objectExpression(properties);
}, createEmotionMacro = function(instancePath) {
  return babelPluginMacros.createMacro(function(_ref) {
    var references = _ref.references, state = _ref.state, babel = _ref.babel;
    _ref.isEmotionCall || (state.emotionSourceMap = !0);
    var t = babel.types;
    Object.keys(references).forEach(function(referenceKey) {
      var isPure = !0, runtimeNode = helperModuleImports.addNamed(state.file.path, referenceKey, instancePath);
      switch (referenceKey) {
       case "injectGlobal":
        isPure = !1;

       case "css":
       case "keyframes":
        references[referenceKey].reverse().forEach(function(reference) {
          var path = reference.parentPath;
          reference.replaceWith(t.cloneDeep(runtimeNode)), isPure && path.addComment("leading", "#__PURE__");
          var node = transformExpressionWithStyles({
            babel: babel,
            state: state,
            path: path,
            shouldLabel: !0
          });
          node && (path.node.arguments[0] = node);
        });
        break;

       default:
        references[referenceKey].reverse().forEach(function(reference) {
          reference.replaceWith(t.cloneDeep(runtimeNode));
        });
      }
    });
  });
}, createStyledMacro = function(_ref) {
  var importPath = _ref.importPath, _ref$originalImportPa = _ref.originalImportPath, originalImportPath = void 0 === _ref$originalImportPa ? importPath : _ref$originalImportPa, isWeb = _ref.isWeb;
  return babelPluginMacros.createMacro(function(_ref2) {
    var references = _ref2.references, state = _ref2.state, babel = _ref2.babel;
    _ref2.isEmotionCall || (state.emotionSourceMap = !0);
    var t = babel.types;
    if (references.default && references.default.length) {
      var _styledIdentifier, originalImportPathStyledIdentifier, getStyledIdentifier = function() {
        return void 0 === _styledIdentifier && (_styledIdentifier = helperModuleImports.addDefault(state.file.path, importPath, {
          nameHint: "styled"
        })), t.cloneDeep(_styledIdentifier);
      }, getOriginalImportPathStyledIdentifier = function() {
        return void 0 === originalImportPathStyledIdentifier && (originalImportPathStyledIdentifier = helperModuleImports.addDefault(state.file.path, originalImportPath, {
          nameHint: "styled"
        })), t.cloneDeep(originalImportPathStyledIdentifier);
      };
      importPath === originalImportPath && (getOriginalImportPathStyledIdentifier = getStyledIdentifier), 
      references.default.forEach(function(reference) {
        var isCall = !1;
        if (t.isMemberExpression(reference.parent) && !1 === reference.parent.computed ? (isCall = !0, 
        reference.parent.property.name.charCodeAt(0) > 96 ? reference.parentPath.replaceWith(t.callExpression(getStyledIdentifier(), [ t.stringLiteral(reference.parent.property.name) ])) : reference.replaceWith(getStyledIdentifier())) : reference.parentPath && reference.parentPath.parentPath && t.isCallExpression(reference.parentPath) && reference.parent.callee === reference.node ? (isCall = !0, 
        reference.replaceWith(getStyledIdentifier())) : reference.replaceWith(getOriginalImportPathStyledIdentifier()), 
        reference.parentPath && reference.parentPath.parentPath) {
          var styledCallPath = reference.parentPath.parentPath, node = transformExpressionWithStyles({
            path: styledCallPath,
            state: state,
            babel: babel,
            shouldLabel: !1
          });
          node && isWeb && (styledCallPath.node.arguments[0] = node);
        }
        isCall && (reference.addComment("leading", "#__PURE__"), isWeb && (reference.parentPath.node.arguments[1] = getStyledOptions(t, reference.parentPath, state)));
      });
    }
    Object.keys(references).filter(function(x) {
      return "default" !== x;
    }).forEach(function(referenceKey) {
      var runtimeNode = helperModuleImports.addNamed(state.file.path, referenceKey, importPath);
      references[referenceKey].reverse().forEach(function(reference) {
        reference.replaceWith(t.cloneDeep(runtimeNode));
      });
    });
  });
}, transformCssCallExpression = function(_ref) {
  var babel = _ref.babel, state = _ref.state, path = _ref.path, sourceMap = _ref.sourceMap, node = transformExpressionWithStyles({
    babel: babel,
    state: state,
    path: path,
    shouldLabel: !0,
    sourceMap: sourceMap
  });
  node ? (path.replaceWith(node), path.hoist()) : path.isCallExpression() && path.addComment("leading", "#__PURE__");
}, cssMacro = babelPluginMacros.createMacro(function(_ref2) {
  var references = _ref2.references, state = _ref2.state, babel = _ref2.babel;
  _ref2.isEmotionCall || (state.emotionSourceMap = !0);
  var t = babel.types;
  references.default && references.default.length && references.default.reverse().forEach(function(reference) {
    state.cssIdentifier || (state.cssIdentifier = helperModuleImports.addDefault(reference, "@emotion/css", {
      nameHint: "css"
    })), reference.replaceWith(t.cloneDeep(state.cssIdentifier)), transformCssCallExpression({
      babel: babel,
      state: state,
      path: reference.parentPath
    });
  }), Object.keys(references).filter(function(x) {
    return "default" !== x;
  }).forEach(function(referenceKey) {
    var runtimeNode = helperModuleImports.addNamed(state.file.path, referenceKey, "@emotion/css", {
      nameHint: referenceKey
    });
    references[referenceKey].reverse().forEach(function(reference) {
      reference.replaceWith(t.cloneDeep(runtimeNode));
    });
  });
}), webStyledMacro = createStyledMacro({
  importPath: "@emotion/styled-base",
  originalImportPath: "@emotion/styled",
  isWeb: !0
}), nativeStyledMacro = createStyledMacro({
  importPath: "@emotion/native",
  originalImportPath: "@emotion/native",
  isWeb: !1
}), primitivesStyledMacro = createStyledMacro({
  importPath: "@emotion/primitives",
  originalImportPath: "@emotion/primitives",
  isWeb: !1
}), macros = {
  createEmotionMacro: createEmotionMacro,
  css: cssMacro,
  createStyledMacro: createStyledMacro
}, emotionCoreMacroThatsNotARealMacro = function(_ref) {
  var references = _ref.references, state = _ref.state, babel = _ref.babel;
  Object.keys(references).forEach(function(refKey) {
    "css" === refKey && references[refKey].forEach(function(path) {
      transformCssCallExpression({
        babel: babel,
        state: state,
        path: path.parentPath
      });
    });
  });
};

function getAbsolutePath(instancePath, rootPath) {
  return "." === instancePath.charAt(0) && nodePath.resolve(rootPath, instancePath);
}

function getInstancePathToCompare(instancePath, rootPath) {
  var absolutePath = getAbsolutePath(instancePath, rootPath);
  return !1 === absolutePath ? instancePath : absolutePath;
}

function index(babel) {
  var t = babel.types;
  return {
    name: "emotion",
    inherits: require("babel-plugin-syntax-jsx"),
    visitor: {
      ImportDeclaration: function(path, state) {
        var dirname = path.hub.file.opts.filename && "unknown" !== path.hub.file.opts.filename ? nodePath.dirname(path.hub.file.opts.filename) : "";
        state.pluginMacros[path.node.source.value] || -1 === state.emotionInstancePaths.indexOf(getInstancePathToCompare(path.node.source.value, dirname)) || (state.pluginMacros[path.node.source.value] = createEmotionMacro(path.node.source.value));
        var pluginMacros = state.pluginMacros;
        if (void 0 !== pluginMacros[path.node.source.value] && !t.isImportNamespaceSpecifier(path.node.specifiers[0])) {
          var imports = path.node.specifiers.map(function(s) {
            return {
              localName: s.local.name,
              importedName: "ImportDefaultSpecifier" === s.type ? "default" : s.imported.name
            };
          }), shouldExit = !1, hasReferences = !1, referencePathsByImportName = imports.reduce(function(byName, _ref2) {
            var importedName = _ref2.importedName, localName = _ref2.localName, binding = path.scope.getBinding(localName);
            return binding ? (byName[importedName] = binding.referencePaths, hasReferences = hasReferences || Boolean(byName[importedName].length), 
            byName) : (shouldExit = !0, byName);
          }, {});
          hasReferences && !shouldExit && (state.file.scope.path.traverse({
            Identifier: function() {}
          }), pluginMacros[path.node.source.value]({
            references: referencePathsByImportName,
            state: state,
            babel: babel,
            isBabelMacrosCall: !0,
            isEmotionCall: !0
          }), pluginMacros[path.node.source.value].keepImport || path.remove());
        }
      },
      Program: function(path, state) {
        if (state.emotionInstancePaths = (state.opts.instances || []).map(function(instancePath) {
          return getInstancePathToCompare(instancePath, process.cwd());
        }), state.pluginMacros = {
          "@emotion/css": cssMacro,
          "@emotion/styled": webStyledMacro,
          "@emotion/core": emotionCoreMacroThatsNotARealMacro,
          "@emotion/primitives": primitivesStyledMacro,
          "@emotion/native": nativeStyledMacro,
          emotion: createEmotionMacro("emotion")
        }, void 0 === state.opts.cssPropOptimization) {
          var _iterator = path.node.body, _isArray = Array.isArray(_iterator), _i = 0;
          for (_iterator = _isArray ? _iterator : _iterator[Symbol.iterator](); ;) {
            var _ref3;
            if (_isArray) {
              if (_i >= _iterator.length) break;
              _ref3 = _iterator[_i++];
            } else {
              if ((_i = _iterator.next()).done) break;
              _ref3 = _i.value;
            }
            var node = _ref3;
            if (t.isImportDeclaration(node) && "@emotion/core" === node.source.value && node.specifiers.some(function(x) {
              return t.isImportSpecifier(x) && "jsx" === x.imported.name;
            })) {
              state.transformCssProp = !0;
              break;
            }
          }
        } else state.transformCssProp = state.opts.cssPropOptimization;
        !1 === state.opts.sourceMap ? state.emotionSourceMap = !1 : state.emotionSourceMap = !0;
      },
      JSXAttribute: function(path, state) {
        if ("css" === path.node.name.name && state.transformCssProp && t.isJSXExpressionContainer(path.node.value) && (t.isObjectExpression(path.node.value.expression) || t.isArrayExpression(path.node.value.expression))) {
          var expressionPath = path.get("value.expression"), sourceMap = state.emotionSourceMap && void 0 !== path.node.loc ? getSourceMap(path.node.loc.start, state) : "";
          expressionPath.replaceWith(t.callExpression(t.identifier("___shouldNeverAppearCSS"), [ path.node.value.expression ])), 
          transformCssCallExpression({
            babel: babel,
            state: state,
            path: expressionPath,
            sourceMap: sourceMap
          }), t.isCallExpression(expressionPath) && (state.cssIdentifier || (state.cssIdentifier = helperModuleImports.addDefault(path, "@emotion/css", {
            nameHint: "css"
          })), expressionPath.get("callee").replaceWith(t.cloneDeep(state.cssIdentifier)));
        }
      },
      CallExpression: {
        exit: function(path, state) {
          try {
            if (path.node.callee && path.node.callee.property && "withComponent" === path.node.callee.property.name) switch (path.node.arguments.length) {
             case 1:
             case 2:
              path.node.arguments[1] = getStyledOptions(t, path, state);
            }
          } catch (e) {
            throw path.buildCodeFrameError(e);
          }
        }
      }
    }
  };
}

emotionCoreMacroThatsNotARealMacro.keepImport = !0, exports.default = index, exports.macros = macros;
