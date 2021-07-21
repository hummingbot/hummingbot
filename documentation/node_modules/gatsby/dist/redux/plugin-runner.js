"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.startPluginRunner = void 0;

var _index = require("./index");

var _apiRunnerNode = _interopRequireDefault(require("../utils/api-runner-node"));

const startPluginRunner = () => {
  _index.emitter.on(`CREATE_PAGE`, action => {
    const page = action.payload;
    (0, _apiRunnerNode.default)(`onCreatePage`, {
      page,
      traceId: action.traceId,
      parentSpan: action.parentSpan
    }, {
      pluginSource: action.plugin.name,
      activity: action.activity
    });
  });
};

exports.startPluginRunner = startPluginRunner;
//# sourceMappingURL=plugin-runner.js.map