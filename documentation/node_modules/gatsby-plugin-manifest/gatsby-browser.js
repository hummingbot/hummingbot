"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

var _gatsby = require("gatsby");

var _getManifestPathname = _interopRequireDefault(require("./get-manifest-pathname"));

/* global __MANIFEST_PLUGIN_HAS_LOCALISATION__ */
// when we don't have localisation in our manifest, we tree shake everything away
if (__MANIFEST_PLUGIN_HAS_LOCALISATION__) {
  exports.onRouteUpdate = function (_ref, pluginOptions) {
    var location = _ref.location;
    var localize = pluginOptions.localize;
    var manifestFilename = (0, _getManifestPathname.default)(location.pathname, localize);
    var manifestEl = document.head.querySelector("link[rel=\"manifest\"]");

    if (manifestEl) {
      manifestEl.setAttribute("href", (0, _gatsby.withPrefix)(manifestFilename));
    }
  };
}