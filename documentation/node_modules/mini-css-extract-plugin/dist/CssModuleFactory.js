"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;

var _CssModule = _interopRequireDefault(require("./CssModule"));

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

class CssModuleFactory {
  // eslint-disable-next-line class-methods-use-this
  create({
    dependencies: [dependency]
  }, callback) {
    callback(null, new _CssModule.default(dependency));
  }

}

exports.default = CssModuleFactory;