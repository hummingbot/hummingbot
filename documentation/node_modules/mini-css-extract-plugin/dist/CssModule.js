"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;

var _webpack = _interopRequireDefault(require("webpack"));

var _utils = require("./utils");

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

const TYPES = new Set([_utils.MODULE_TYPE]);
const CODE_GENERATION_RESULT = {
  sources: new Map(),
  runtimeRequirements: new Set()
};

class CssModule extends _webpack.default.Module {
  constructor({
    context,
    identifier,
    identifierIndex,
    content,
    media,
    sourceMap
  }) {
    super(_utils.MODULE_TYPE, context);
    this.id = '';
    this._context = context;
    this._identifier = identifier;
    this._identifierIndex = identifierIndex;
    this.content = content;
    this.media = media;
    this.sourceMap = sourceMap;
    this.buildInfo = {};
    this.buildMeta = {};
  } // no source() so webpack 4 doesn't do add stuff to the bundle


  size() {
    return this.content.length;
  }

  identifier() {
    return `css ${this._identifier} ${this._identifierIndex}`;
  }

  readableIdentifier(requestShortener) {
    return `css ${requestShortener.shorten(this._identifier)}${this._identifierIndex ? ` (${this._identifierIndex})` : ''}`;
  } // eslint-disable-next-line class-methods-use-this


  getSourceTypes() {
    return TYPES;
  } // eslint-disable-next-line class-methods-use-this


  codeGeneration() {
    return CODE_GENERATION_RESULT;
  }

  nameForCondition() {
    const resource = this._identifier.split('!').pop();

    const idx = resource.indexOf('?');

    if (idx >= 0) {
      return resource.substring(0, idx);
    }

    return resource;
  }

  updateCacheModule(module) {
    this.content = module.content;
    this.media = module.media;
    this.sourceMap = module.sourceMap;
  } // eslint-disable-next-line class-methods-use-this


  needRebuild() {
    return true;
  } // eslint-disable-next-line class-methods-use-this


  needBuild(context, callback) {
    callback(null, false);
  }

  build(options, compilation, resolver, fileSystem, callback) {
    this.buildInfo = {};
    this.buildMeta = {};
    callback();
  }

  updateHash(hash, context) {
    super.updateHash(hash, context);
    hash.update(this.content);
    hash.update(this.media || '');
    hash.update(this.sourceMap ? JSON.stringify(this.sourceMap) : '');
  }

  serialize(context) {
    const {
      write
    } = context;
    write(this._context);
    write(this._identifier);
    write(this._identifierIndex);
    write(this.content);
    write(this.media);
    write(this.sourceMap);
    super.serialize(context);
  }

  deserialize(context) {
    super.deserialize(context);
  }

}

if (_webpack.default.util && _webpack.default.util.serialization) {
  _webpack.default.util.serialization.register(CssModule, 'mini-css-extract-plugin/dist/CssModule', null, {
    serialize(instance, context) {
      instance.serialize(context);
    },

    deserialize(context) {
      const {
        read
      } = context;
      const dep = new CssModule({
        context: read(),
        identifier: read(),
        identifierIndex: read(),
        content: read(),
        media: read(),
        sourceMap: read()
      });
      dep.deserialize(context);
      return dep;
    }

  });
}

var _default = CssModule;
exports.default = _default;