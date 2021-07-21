"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.statusReducer = void 0;

var _lodash = _interopRequireDefault(require("lodash"));

const defaultState = {
  PLUGINS_HASH: ``,
  plugins: {}
};

const statusReducer = (state = defaultState, action) => {
  var _action$plugin;

  switch (action.type) {
    case `DELETE_CACHE`:
      return defaultState;

    case `UPDATE_PLUGINS_HASH`:
      return { ...state,
        PLUGINS_HASH: action.payload
      };

    case `SET_PLUGIN_STATUS`:
      if (!action.plugin || !((_action$plugin = action.plugin) === null || _action$plugin === void 0 ? void 0 : _action$plugin.name)) {
        throw new Error(`You can't set plugin status without a plugin`);
      }

      if (!_lodash.default.isObject(action.payload)) {
        throw new Error(`You must pass an object into setPluginStatus. What was passed in was ${JSON.stringify(action.payload, null, 4)}`);
      }

      return { ...state,
        plugins: { ...state.plugins,
          [action.plugin.name]: _lodash.default.merge({}, state.plugins[action.plugin.name], action.payload)
        }
      };

    default:
      return state;
  }
};

exports.statusReducer = statusReducer;
//# sourceMappingURL=status.js.map