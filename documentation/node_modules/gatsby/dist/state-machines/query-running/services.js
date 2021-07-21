"use strict";

exports.__esModule = true;
exports.queryRunningServices = void 0;

var _services = require("../../services");

const queryRunningServices = {
  extractQueries: _services.extractQueries,
  writeOutRequires: _services.writeOutRequires,
  calculateDirtyQueries: _services.calculateDirtyQueries,
  runStaticQueries: _services.runStaticQueries,
  runPageQueries: _services.runPageQueries,
  waitUntilAllJobsComplete: _services.waitUntilAllJobsComplete,
  writeOutRedirects: _services.writeOutRedirects,
  rebuildSchemaWithSitePage: _services.rebuildSchemaWithSitePage
};
exports.queryRunningServices = queryRunningServices;
//# sourceMappingURL=services.js.map