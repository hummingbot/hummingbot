"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.babelrcReducer = void 0;

var _lodash = _interopRequireDefault(require("lodash"));

const babelrcReducer = (state = {
  stages: {
    develop: {
      plugins: [],
      presets: [],
      options: {
        cacheDirectory: true,
        sourceType: `unambiguous`
      }
    },
    "develop-html": {
      plugins: [],
      presets: [],
      options: {
        cacheDirectory: true,
        sourceType: `unambiguous`
      }
    },
    "build-html": {
      plugins: [],
      presets: [],
      options: {
        cacheDirectory: true,
        sourceType: `unambiguous`
      }
    },
    "build-javascript": {
      plugins: [],
      presets: [],
      options: {
        cacheDirectory: true,
        sourceType: `unambiguous`
      }
    }
  }
}, action) => {
  switch (action.type) {
    case `SET_BABEL_PLUGIN`:
      {
        Object.keys(state.stages).forEach(stage => {
          if (action.payload.stage && action.payload.stage !== stage) {
            return;
          }

          const index = _lodash.default.findIndex(state.stages[stage].plugins, plugin => plugin.name === action.payload.name); // If the plugin already exists, merge the options.
          // Otherwise, add it to the end.


          if (index !== -1) {
            const plugin = state.stages[stage].plugins[index];
            state.stages[stage].plugins[index] = {
              name: plugin.name,
              options: _lodash.default.merge(plugin.options, action.payload.options)
            };
          } else {
            state.stages[stage].plugins = [...state.stages[stage].plugins, action.payload];
          }
        });
        return state;
      }

    case `SET_BABEL_PRESET`:
      {
        Object.keys(state.stages).forEach(stage => {
          if (action.payload.stage && action.payload.stage !== stage) {
            return;
          }

          const index = _lodash.default.findIndex(state.stages[stage].presets, plugin => plugin.name === action.payload.name); // If the plugin already exists, merge the options.
          // Otherwise, add it to the end.


          if (index !== -1) {
            const plugin = state.stages[stage].presets[index];
            state.stages[stage].presets[index] = {
              name: plugin.name,
              options: _lodash.default.merge(plugin.options, action.payload.options)
            };
          } else {
            state.stages[stage].presets = [...state.stages[stage].presets, action.payload];
          }
        });
        return state;
      }

    case `SET_BABEL_OPTIONS`:
      {
        Object.keys(state.stages).forEach(stage => {
          if (action.payload.stage && action.payload.stage !== stage) {
            return;
          }

          state.stages[stage].options = { ...state.stages[stage].options,
            ...action.payload.options
          };
        });
        return state;
      }
  }

  return state;
};

exports.babelrcReducer = babelrcReducer;
//# sourceMappingURL=babelrc.js.map