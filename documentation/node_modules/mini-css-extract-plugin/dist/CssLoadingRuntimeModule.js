"use strict";

var _webpack = require("webpack");

var _utils = require("./utils");

const {
  comparators: {
    compareModulesByIdentifier
  }
} = _webpack.util;

const getCssChunkObject = (mainChunk, compilation) => {
  const obj = {};
  const {
    chunkGraph
  } = compilation;

  for (const chunk of mainChunk.getAllAsyncChunks()) {
    const modules = chunkGraph.getOrderedChunkModulesIterable(chunk, compareModulesByIdentifier);

    for (const module of modules) {
      if (module.type === _utils.MODULE_TYPE) {
        obj[chunk.id] = 1;
        break;
      }
    }
  }

  return obj;
};

module.exports = class CssLoadingRuntimeModule extends _webpack.RuntimeModule {
  constructor(runtimeRequirements) {
    super('css loading', 10);
    this.runtimeRequirements = runtimeRequirements;
  }

  generate() {
    const {
      chunk,
      compilation,
      runtimeRequirements
    } = this;
    const {
      runtimeTemplate,
      outputOptions: {
        crossOriginLoading
      }
    } = compilation;
    const chunkMap = getCssChunkObject(chunk, compilation);
    const withLoading = runtimeRequirements.has(_webpack.RuntimeGlobals.ensureChunkHandlers) && Object.keys(chunkMap).length > 0;
    const withHmr = runtimeRequirements.has(_webpack.RuntimeGlobals.hmrDownloadUpdateHandlers);
    if (!withLoading && !withHmr) return null;
    return _webpack.Template.asString([`var createStylesheet = ${runtimeTemplate.basicFunction('fullhref, resolve, reject', ['var linkTag = document.createElement("link");', 'linkTag.rel = "stylesheet";', 'linkTag.type = "text/css";', 'linkTag.onload = resolve;', 'linkTag.onerror = function(event) {', _webpack.Template.indent(['var request = event && event.target && event.target.src || fullhref;', 'var err = new Error("Loading CSS chunk " + chunkId + " failed.\\n(" + request + ")");', 'err.code = "CSS_CHUNK_LOAD_FAILED";', 'err.request = request;', 'linkTag.parentNode.removeChild(linkTag)', 'reject(err);']), '};', 'linkTag.href = fullhref;', crossOriginLoading ? _webpack.Template.asString([`if (linkTag.href.indexOf(window.location.origin + '/') !== 0) {`, _webpack.Template.indent(`linkTag.crossOrigin = ${JSON.stringify(crossOriginLoading)};`), '}']) : '', 'var head = document.getElementsByTagName("head")[0];', 'head.appendChild(linkTag);', 'return linkTag;'])};`, `var findStylesheet = ${runtimeTemplate.basicFunction('href, fullhref', ['var existingLinkTags = document.getElementsByTagName("link");', 'for(var i = 0; i < existingLinkTags.length; i++) {', _webpack.Template.indent(['var tag = existingLinkTags[i];', 'var dataHref = tag.getAttribute("data-href") || tag.getAttribute("href");', 'if(tag.rel === "stylesheet" && (dataHref === href || dataHref === fullhref)) return tag;']), '}', 'var existingStyleTags = document.getElementsByTagName("style");', 'for(var i = 0; i < existingStyleTags.length; i++) {', _webpack.Template.indent(['var tag = existingStyleTags[i];', 'var dataHref = tag.getAttribute("data-href");', 'if(dataHref === href || dataHref === fullhref) return tag;']), '}'])};`, `var loadStylesheet = ${runtimeTemplate.basicFunction('chunkId', `return new Promise(${runtimeTemplate.basicFunction('resolve, reject', [`var href = ${_webpack.RuntimeGlobals.require}.miniCssF(chunkId);`, `var fullhref = ${_webpack.RuntimeGlobals.publicPath} + href;`, 'if(findStylesheet(href, fullhref)) return resolve();', 'createStylesheet(fullhref, resolve, reject);'])});`)}`, withLoading ? _webpack.Template.asString(['// object to store loaded CSS chunks', 'var installedCssChunks = {', _webpack.Template.indent(chunk.ids.map(id => `${JSON.stringify(id)}: 0`).join(',\n')), '};', '', `${_webpack.RuntimeGlobals.ensureChunkHandlers}.miniCss = ${runtimeTemplate.basicFunction('chunkId, promises', [`var cssChunks = ${JSON.stringify(chunkMap)};`, 'if(installedCssChunks[chunkId]) promises.push(installedCssChunks[chunkId]);', 'else if(installedCssChunks[chunkId] !== 0 && cssChunks[chunkId]) {', _webpack.Template.indent([`promises.push(installedCssChunks[chunkId] = loadStylesheet(chunkId).then(${runtimeTemplate.basicFunction('', 'installedCssChunks[chunkId] = 0;')}, ${runtimeTemplate.basicFunction('e', ['delete installedCssChunks[chunkId];', 'throw e;'])}));`]), '}'])};`]) : '// no chunk loading', '', withHmr ? _webpack.Template.asString(['var oldTags = [];', 'var newTags = [];', `var applyHandler = ${runtimeTemplate.basicFunction('options', [`return { dispose: ${runtimeTemplate.basicFunction('', ['for(var i = 0; i < oldTags.length; i++) {', _webpack.Template.indent(['var oldTag = oldTags[i];', 'if(oldTag.parentNode) oldTag.parentNode.removeChild(oldTag);']), '}', 'oldTags.length = 0;'])}, apply: ${runtimeTemplate.basicFunction('', ['for(var i = 0; i < newTags.length; i++) newTags[i].rel = "stylesheet";', 'newTags.length = 0;'])} };`])}`, `${_webpack.RuntimeGlobals.hmrDownloadUpdateHandlers}.miniCss = ${runtimeTemplate.basicFunction('chunkIds, removedChunks, removedModules, promises, applyHandlers, updatedModulesList', ['applyHandlers.push(applyHandler);', `chunkIds.forEach(${runtimeTemplate.basicFunction('chunkId', [`var href = ${_webpack.RuntimeGlobals.require}.miniCssF(chunkId);`, `var fullhref = ${_webpack.RuntimeGlobals.publicPath} + href;`, 'const oldTag = findStylesheet(href, fullhref);', 'if(!oldTag) return;', `promises.push(new Promise(${runtimeTemplate.basicFunction('resolve, reject', [`var tag = createStylesheet(fullhref, ${runtimeTemplate.basicFunction('', ['tag.as = "style";', 'tag.rel = "preload";', 'resolve();'])}, reject);`, 'oldTags.push(oldTag);', 'newTags.push(tag);'])}));`])});`])}`]) : '// no hmr']);
  }

};