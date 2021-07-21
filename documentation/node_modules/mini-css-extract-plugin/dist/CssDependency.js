"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;

var _webpack = _interopRequireDefault(require("webpack"));

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

class CssDependency extends _webpack.default.Dependency {
  constructor({
    identifier,
    content,
    media,
    sourceMap
  }, context, identifierIndex) {
    super();
    this.identifier = identifier;
    this.identifierIndex = identifierIndex;
    this.content = content;
    this.media = media;
    this.sourceMap = sourceMap;
    this.context = context;
  }

  getResourceIdentifier() {
    return `css-module-${this.identifier}-${this.identifierIndex}`;
  }

  serialize(context) {
    const {
      write
    } = context;
    write(this.identifier);
    write(this.content);
    write(this.media);
    write(this.sourceMap);
    write(this.context);
    write(this.identifierIndex);
    super.serialize(context);
  }

  deserialize(context) {
    super.deserialize(context);
  }

}

if (_webpack.default.util && _webpack.default.util.serialization) {
  _webpack.default.util.serialization.register(CssDependency, 'mini-css-extract-plugin/dist/CssDependency', null, {
    serialize(instance, context) {
      instance.serialize(context);
    },

    deserialize(context) {
      const {
        read
      } = context;
      const dep = new CssDependency({
        identifier: read(),
        content: read(),
        media: read(),
        sourceMap: read()
      }, read(), read());
      dep.deserialize(context);
      return dep;
    }

  });
}

var _default = CssDependency;
exports.default = _default;