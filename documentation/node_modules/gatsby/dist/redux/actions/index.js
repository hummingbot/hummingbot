"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard");

exports.__esModule = true;
exports.internalActions = exports.restrictedActionsAvailableInAPI = exports.boundActionCreators = exports.actions = void 0;

var _redux = require("redux");

var _ = require("..");

var internalActions = _interopRequireWildcard(require("./internal"));

exports.internalActions = internalActions;

var _public = require("./public");

exports.publicActions = _public.actions;

var _restricted = require("./restricted");

exports.restrictedActions = _restricted.actions;
const actions = { ...internalActions,
  ..._public.actions,
  ..._restricted.actions
}; // Deprecated, remove in v3

exports.actions = actions;
const boundActionCreators = (0, _redux.bindActionCreators)(actions, _.store.dispatch);
exports.boundActionCreators = boundActionCreators;
const restrictedActionsAvailableInAPI = _restricted.availableActionsByAPI;
exports.restrictedActionsAvailableInAPI = restrictedActionsAvailableInAPI;
//# sourceMappingURL=index.js.map