"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.pagesReducer = void 0;

var _normalizePath = _interopRequireDefault(require("normalize-path"));

const pagesReducer = (state = new Map(), action) => {
  switch (action.type) {
    case `DELETE_CACHE`:
      return new Map();

    case `CREATE_PAGE`:
      {
        var _action$plugin, _action$plugin$id, _action$plugin$id2;

        action.payload.component = (0, _normalizePath.default)(action.payload.component); // throws an error if the page is not created by a plugin

        if (!((_action$plugin = action.plugin) === null || _action$plugin === void 0 ? void 0 : _action$plugin.name)) {
          console.log(``);
          console.error(JSON.stringify(action, null, 4));
          console.log(``);
          throw new Error(`Pages can only be created by plugins. There wasn't a plugin set when creating this page.`);
        } // Link page to its plugin.


        action.payload.pluginCreator___NODE = (_action$plugin$id = action.plugin.id) !== null && _action$plugin$id !== void 0 ? _action$plugin$id : ``;
        action.payload.pluginCreatorId = (_action$plugin$id2 = action.plugin.id) !== null && _action$plugin$id2 !== void 0 ? _action$plugin$id2 : ``; // Add page to the state with the path as key

        state.set(action.payload.path, action.payload);
        return state;
      }

    case `DELETE_PAGE`:
      {
        state.delete(action.payload.path);
        return state;
      }

    default:
      return state;
  }
};

exports.pagesReducer = pagesReducer;
//# sourceMappingURL=pages.js.map